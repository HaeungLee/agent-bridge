import datetime
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Any
from agent_bridge.config import find_project_root, load_all_configs
from agent_bridge.contracts import DecisionReport, TestSummary, validate_decision_report
from agent_bridge.runners.cli_adapter import CliAdapterRunner, load_cli_adapter_config, make_local_smoke_config
from agent_bridge.runners.mock_subprocess import MockSubprocessRunner
from agent_bridge.task_spec import DEFAULT_EXECUTION_MODE, load_task_spec, validate_task_spec
from agent_bridge.worktrees import (
    WorktreeInfo,
    collect_worktree_changed_files,
    create_isolated_worktree,
    export_worktree_patch,
    remove_isolated_worktree,
    write_worktree_metadata,
)

COMPLETED_MARKER = "completed.marker"
DECISION_REPORT_STATUS_MAP = {
    "completed": "completed",
    "failed": "failed",
    "timeout": "timeout",
    "blocked": "blocked",
    "partial": "completed",
    "needs_approval": "blocked",
}

def write_json(path: Path, data: Any) -> None:
    """
    Writes data in JSON format to the specified path.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def write_text(path: Path, text: str) -> None:
    """
    Writes text content to the specified path.
    """
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def find_latest_run(root_path: Path) -> Path:
    """
    Finds the latest completed run directory under .agent/runs/.
    A run is considered completed only after completed.marker is written.
    Raises FileNotFoundError if no completed run directories exist.
    """
    runs_dir = root_path / ".agent" / "runs"
    if not runs_dir.exists():
        raise FileNotFoundError("No run directory exists because .agent/runs is missing")

    run_dirs = [
        d for d in runs_dir.iterdir()
        if d.is_dir() and (d / COMPLETED_MARKER).exists()
    ]
    if not run_dirs:
        raise FileNotFoundError("No completed run directories found under .agent/runs")

    run_dirs.sort(key=lambda x: x.name, reverse=True)
    return run_dirs[0]

def generate_run_id(agent_name: str) -> str:
    """
    Generates a unique run ID based on current time, a short UUID suffix, and agent name.
    Format: YYYYMMDD-HHMMSS-xxxxxx-agent_name
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    sanitized_agent = "".join(c for c in agent_name if c.isalnum() or c in ("_", "-")).lower()
    return f"{timestamp}-{suffix}-{sanitized_agent}"

def normalize_report_status(runner_status: str) -> str:
    """
    Maps runner-specific statuses into decision_report.v0 statuses.
    """
    return DECISION_REPORT_STATUS_MAP.get(runner_status, "failed")

def create_run_directory(run_id: str, root_path: Optional[Path] = None) -> Path:
    """
    Creates a run directory under .agent/runs/<run_id>.
    Also creates a raw/ subdirectory inside.
    Raises FileExistsError if the directory or raw/ subdirectory already exists.
    """
    if root_path is None:
        root_path = find_project_root()
        
    runs_dir = root_path / ".agent" / "runs"
    run_path = runs_dir / run_id
    raw_path = run_path / "raw"
    
    os.makedirs(raw_path, exist_ok=False)
    return run_path

def setup_agent_directories(root_path: Optional[Path] = None) -> None:
    """
    Ensures that the basic .agent directory structure exists.
    Directories: tasks, runs, reports, metrics
    """
    if root_path is None:
        root_path = find_project_root()
        
    agent_dir = root_path / ".agent"
    for subdir in ["tasks", "runs", "reports", "metrics", "sessions"]:
        os.makedirs(agent_dir / subdir, exist_ok=True)

def execute_mock_run(agent_name: str, task_path: Path, workspace_path: Path, root_path: Optional[Path] = None) -> str:
    """
    Executes a mock run lifecycle:
    1. Validates presence of agent in config, task file existence, workspace directory existence, and runs dir writability.
    2. Generates run ID and creates directory structure.
    3. Writes request.json, decision_report.json, summary.md, process.md, stdout.txt, and stderr.txt.
    4. Writes metrics.json, touched_files.json, diffstat.txt, tests.md, and risks.md.
    """
    if root_path is None:
        root_path = find_project_root()
        
    files_inspected_val = []
    files_changed_val = []
    task_spec = _load_optional_task_spec(task_path)
    execution_mode = _task_execution_mode(task_spec)

    # 1. Verification
    # A. Config validation
    configs = load_all_configs(root_path)
    agents = configs.get("agents", {}).get("agents", {})
    if agent_name not in agents:
        raise ValueError(f"Agent '{agent_name}' is not configured in config/agents.toml")
        
    agent_info = agents[agent_name]
    
    # B. Task validation
    if not task_path.exists():
        raise FileNotFoundError(f"Task file '{task_path}' does not exist")
    if not task_path.is_file():
        raise ValueError(f"Task path '{task_path}' is not a file")
        
    # C. Workspace validation
    if not workspace_path.exists():
        raise FileNotFoundError(f"Workspace path '{workspace_path}' does not exist")
    if not workspace_path.is_dir():
        raise ValueError(f"Workspace path '{workspace_path}' is not a directory")
        
    # D. .agent/runs writability
    runs_dir = root_path / ".agent" / "runs"
    os.makedirs(runs_dir, exist_ok=True)
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(prefix=".write_check_", dir=runs_dir)
        with os.fdopen(fd, "w") as f:
            f.write("check")
    except Exception as e:
        raise PermissionError(f"Directory '.agent/runs' is not writable: {e}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        
    # 2. Setup run ID & directory with collision retry
    max_retries = 3
    for attempt in range(max_retries):
        try:
            run_id = generate_run_id(agent_name)
            run_dir = create_run_directory(run_id, root_path)
            break
        except FileExistsError as e:
            if attempt == max_retries - 1:
                raise FileExistsError(f"Failed to create a unique run directory after {max_retries} attempts: {e}")
            import time
            time.sleep(0.01)
    
    worktree_info: WorktreeInfo | None = None
    execution_workspace_path = workspace_path
    runner_name = agent_info.get("runner", "unknown")
    status_val = "failed"
    verdict_val = "BLOCKED"
    summary_val = "Run did not start."
    commands_run_val: list[str] = []
    runtime_sec = 0.0
    stdout_val = ""
    stderr_val = ""
    metadata_val: dict[str, Any] = {}
    risks_list: list[str] = []
    open_questions_list: list[str] = []
    next_action_val = "Review run artifacts and retry after fixing the orchestration failure."
    confidence_val = 0.0
    orchestration_errors: list[str] = []

    try:
        if execution_mode == "worktree_patch":
            worktree_info = create_isolated_worktree(workspace_path, run_id)
            write_worktree_metadata(worktree_info, run_dir / "worktree.json")
            execution_workspace_path = worktree_info.worktree_path

        # 3. Create request.json
        request_data = {
            "agent": agent_name,
            "task": str(task_path),
            "workspace": str(workspace_path),
            "execution_workspace": str(execution_workspace_path),
            "execution_mode": execution_mode,
            "timestamp": datetime.datetime.now().isoformat()
        }
        write_json(run_dir / "request.json", request_data)

        # 4. Check runner and execute
        if runner_name == "mock_subprocess":
            # Execute safe local python subprocess
            runner = MockSubprocessRunner()
            # default timeout: 5 seconds for smoke testing
            res = runner.run(task_path, execution_workspace_path, timeout_seconds=5)

            status_val = normalize_report_status(res.status)
            if status_val == "completed":
                verdict_val = "NEEDS_DECISION"
            else:
                verdict_val = "BLOCKED"

            summary_val = f"Mock subprocess run result: {res.summary}"
            commands_run_val = res.commands_run
            runtime_sec = res.runtime_seconds
            stdout_val = res.stdout
            stderr_val = res.stderr
            metadata_val = res.metadata or {}

            risks_list = ["Phase 3: Execution under safe local mock_subprocess. No external coding agent invoked."]
            if status_val == "timeout":
                risks_list.append("Subprocess execution timed out before completion.")

            open_questions_list = ["When will Gemini or active coding agents be integrated?"]
            next_action_val = "Proceed to Phase 4 for router memory or Phase 5 workflow."
            confidence_val = 0.8 if status_val == "completed" else 0.0
        elif runner_name == "cli_adapter":
            adapter_id = agent_info.get("adapter_id", agent_name)
            if adapter_id == "cli_smoke":
                adapter_config = make_local_smoke_config()
            else:
                adapter_config = load_cli_adapter_config(configs.get("runners", {}), adapter_id)
            runner = CliAdapterRunner(adapter_id=adapter_id, config=adapter_config)
            res = runner.run(task_path, execution_workspace_path, timeout_seconds=int(adapter_config.timeout_ms / 1000))

            status_val = normalize_report_status(res.status)
            verdict_val = "NEEDS_DECISION" if status_val == "completed" else "BLOCKED"
            summary_val = f"CLI adapter run result: {res.summary}"
            commands_run_val = res.commands_run
            runtime_sec = res.runtime_seconds
            stdout_val = res.stdout
            stderr_val = res.stderr
            metadata_val = res.metadata or {}
            risks_list = ["Phase 5-B: CLI adapter smoke. External CLI may be invoked if configured."]
            if status_val != "completed":
                risks_list.append("CLI adapter did not complete successfully.")
            open_questions_list = ["When should write-capable agent execution be enabled?"]
            next_action_val = "Review CLI adapter smoke and result scope check before enabling write-capable adapters."
            confidence_val = 0.7 if status_val == "completed" else 0.0

            xml_data = None
            final_report = ""
            adapter_artifacts = metadata_val.get("adapter_artifacts") or []
            for art in adapter_artifacts:
                if art.get("kind") == "xml_report_parsed":
                    try:
                        xml_data = json.loads(art.get("text", "{}"))
                    except Exception:
                        pass
                if art.get("kind") == "final_report":
                    final_report = str(art.get("text") or "").strip()

            if xml_data:
                if xml_data.get("summary"):
                    summary_val = xml_data["summary"]
                files_inspected_val = xml_data.get("files_inspected") or []
                files_changed_val = xml_data.get("files_changed") or []
                if xml_data.get("risks"):
                    risks_list = xml_data["risks"]
                if xml_data.get("open_questions"):
                    open_questions_list = xml_data["open_questions"]
                if xml_data.get("next_step"):
                    next_action_val = xml_data["next_step"]
            elif final_report:
                summary_val = _compact_text(final_report)
        else:
            # Default blocked behavior for non-mock runners
            status_val = "blocked"
            verdict_val = "BLOCKED"
            summary_val = "This run is blocked because the agent is configured with a non-mock runner, which is not implemented in this phase."
            commands_run_val = []
            runtime_sec = 0.0
            stdout_val = "This run is blocked: non-mock runner configuration detected.\n"
            stderr_val = "Subprocess not executed: runner blocked as intended.\n"
            metadata_val = {}
            risks_list = ["The selected agent uses a runner that is currently blocked or not integrated in this phase."]
            open_questions_list = ["When will the integrated runner be enabled for production workflows?"]
            next_action_val = "Configure the agent to use a supported runner or implement the corresponding runner adapter."
            confidence_val = 0.0

        if worktree_info is not None:
            files_changed_val = collect_worktree_changed_files(worktree_info)
            export_worktree_patch(worktree_info, run_dir / "patch.diff")
    except Exception as exc:
        orchestration_errors.append(f"{type(exc).__name__}: {exc}")
        status_val = "failed"
        verdict_val = "BLOCKED"
        summary_val = f"Run orchestration failed: {exc}"
        stderr_val = f"{stderr_val}\nRun orchestration failed: {type(exc).__name__}: {exc}\n".lstrip()
        risks_list = ["Run orchestration failed before normal artifact completion."]
        if execution_mode == "worktree_patch":
            risks_list.append("Worktree patch artifacts may be missing or incomplete.")
        open_questions_list = ["Inspect raw/stderr.txt and orchestration_errors.json before retrying."]
        next_action_val = "Fix the orchestration failure, then rerun the task."
        confidence_val = 0.0
    finally:
        if worktree_info is not None and not _keep_worktree_enabled():
            try:
                remove_isolated_worktree(worktree_info, force=True)
            except Exception as cleanup_exc:
                orchestration_errors.append(f"cleanup {type(cleanup_exc).__name__}: {cleanup_exc}")

    if orchestration_errors:
        write_json(run_dir / "orchestration_errors.json", orchestration_errors)
        if status_val == "completed":
            status_val = "failed"
            verdict_val = "BLOCKED"
            summary_val = "Run completed, but orchestration cleanup or artifact export failed."
            risks_list.append("Run orchestration reported errors after runner execution.")
            open_questions_list.append("Inspect orchestration_errors.json before trusting this run.")
            next_action_val = "Fix the orchestration error, then rerun the task."
            confidence_val = 0.0

    request_path = run_dir / "request.json"
    if not request_path.exists():
        request_data = {
            "agent": agent_name,
            "task": str(task_path),
            "workspace": str(workspace_path),
            "execution_workspace": str(execution_workspace_path),
            "execution_mode": execution_mode,
            "timestamp": datetime.datetime.now().isoformat(),
            "orchestration_errors": orchestration_errors,
        }
        write_json(request_path, request_data)

    report = DecisionReport(
        run_id=run_id,
        agent=agent_name,
        runner=runner_name,
        provider=agent_info.get("provider", "unknown"),
        model=agent_info.get("model", "unknown"),
        role=agent_info.get("role", "unknown"),
        mode=agent_info.get("default_mode", "mock"),
        status=status_val,
        verdict=verdict_val,
        summary=summary_val,
        files_inspected=files_inspected_val,
        files_changed=files_changed_val,
        commands_run=commands_run_val,
        tests=TestSummary(status="not_run", summary="Not run. This is runner execution, not project verification."),
        risks=risks_list,
        open_questions=open_questions_list,
        next_action=next_action_val,
        confidence=confidence_val
    )
    
    # Validate report before writing
    report_dict = report.to_dict()
    validate_decision_report(report_dict)
    write_json(run_dir / "decision_report.json", report_dict)
    
    # 5. Create summary.md
    summary_content = f"""# Run Summary: {run_id}

- **Agent**: {agent_name}
- **Runner**: {report.runner}
- **Provider**: {report.provider}
- **Model**: {report.model}
- **Status**: {report.status}
- **Verdict**: {report.verdict}

## Result

{report.summary}

### Risks

"""
    for r in report.risks:
        summary_content += f"- {r}\n"
    write_text(run_dir / "summary.md", summary_content)
    
    # 6. Create process.md
    process_content = f"""# Run Process Log: {run_id}

## Run Metadata

- Run ID: {run_id}
- Agent: {agent_name}
- Runner: {report.runner}
- Provider: {report.provider}
- Model: {report.model}
- Role: {report.role}
- Task: {task_path}
- Workspace: {workspace_path}
- Execution Workspace: {execution_workspace_path}
- Execution Mode: {execution_mode}
- Status: {report.status}

## Objective

Verify that the `agent-bridge run` CLI life cycle successfully executes, performs initial file validations, directories provisioning, and exports normalized contracts without side effects.

## Result

{report.summary}

## Risks

"""
    for r in report.risks:
        process_content += f"- {r}\n"
    process_content += "\n## Open Questions\n\n"
    for q in report.open_questions:
        process_content += f"- {q}\n"
        
    write_text(run_dir / "process.md", process_content)
    
    # 7. Create raw/stdout.txt & raw/stderr.txt
    write_text(run_dir / "raw" / "stdout.txt", stdout_val)
    write_text(run_dir / "raw" / "stderr.txt", stderr_val)
    
    # 8. Create metrics.json
    metrics_data = {
        "agent": agent_name,
        "runner": report.runner,
        "provider": report.provider,
        "model": report.model,
        "task_type": report.role,
        "workspace": str(workspace_path),
        "execution_workspace": str(execution_workspace_path),
        "execution_mode": execution_mode,
        "files_inspected": len(files_inspected_val),
        "files_changed": len(files_changed_val),
        "lines_added": 0,
        "lines_deleted": 0,
        "commands_run": len(commands_run_val),
        "test_status": "unknown",
        "runtime_seconds": runtime_sec,
        "estimated_cost_usd": 0.0,
        "tokens_in": None,
        "tokens_out": None,
        "session_id": metadata_val.get("session_id"),
        "session_reused": metadata_val.get("session_reused"),
        "session_policy": metadata_val.get("session_policy"),
        "session_name": metadata_val.get("session_name"),
        "orchestration_errors": len(orchestration_errors),
        "commander_verdict": None,
        "user_verdict": None
    }
    write_json(run_dir / "metrics.json", metrics_data)
    
    # 9. Create touched_files.json
    write_json(run_dir / "touched_files.json", files_changed_val)
    
    # 10. Create diffstat.txt
    if execution_mode == "worktree_patch":
        write_text(run_dir / "diffstat.txt", f"{len(files_changed_val)} files changed (worktree patch exported)\n")
    else:
        write_text(run_dir / "diffstat.txt", "0 files changed, 0 insertions(+), 0 deletions(-)\n")
    
    # 11. Create tests.md
    cmd_list_str = "\n".join(f"- {cmd}" for cmd in commands_run_val) if commands_run_val else "No commands executed."
    tests_content = f"""# Run Tests: {run_id}

## Commands Executed

{cmd_list_str}

## Results

- **Test Status**: {report.tests.status}
- **Summary**: {report.tests.summary}
"""
    write_text(run_dir / "tests.md", tests_content)
    
    # 12. Create risks.md
    risks_content = f"# Run Risks: {run_id}\n\n"
    for r in report.risks:
        risks_content += f"- {r}\n"
    write_text(run_dir / "risks.md", risks_content)

    # Save structured adapter report artifacts that are useful for commander review.
    if runner_name == "cli_adapter" and status_val == "completed":
        adapter_artifacts = metadata_val.get("adapter_artifacts") or []
        xml_data = None
        for art in adapter_artifacts:
            kind = art.get("kind")
            if kind == "final_report":
                final_report = str(art.get("text") or "").strip()
                if final_report:
                    write_text(run_dir / "final_report.md", final_report)
            elif kind == "xml_report_parsed":
                try:
                    xml_data = json.loads(art.get("text", "{}"))
                except Exception:
                    pass
            elif kind == "xml_report_raw":
                xml_text = art.get("text", "")
                if xml_text.strip():
                    write_text(run_dir / "response.xml", xml_text)

        if xml_data and "commands_run" in xml_data:
            write_json(run_dir / "claimed_commands.json", xml_data["commands_run"])

    marker_content = {
        "run_id": run_id,
        "completed_at": datetime.datetime.now().isoformat(),
        "status": report.status,
        "verdict": report.verdict,
        "session_id": metadata_val.get("session_id"),
    }
    write_json(run_dir / COMPLETED_MARKER, marker_content)
    
    return run_id


def _compact_text(text: str, limit: int = 1800) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "..."


def _load_optional_task_spec(task_path: Path) -> dict[str, Any] | None:
    spec_path = task_path.with_suffix(".toml")
    if not spec_path.exists():
        return None
    spec = load_task_spec(spec_path)
    validate_task_spec(spec)
    return spec


def _task_execution_mode(spec: dict[str, Any] | None) -> str:
    if spec is None:
        return DEFAULT_EXECUTION_MODE
    return str(spec.get("execution_mode", DEFAULT_EXECUTION_MODE)).strip() or DEFAULT_EXECUTION_MODE


def _keep_worktree_enabled() -> bool:
    return os.environ.get("AGENT_BRIDGE_KEEP_WORKTREE", "").strip().lower() in {"1", "true", "yes"}
