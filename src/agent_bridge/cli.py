import argparse
import sys
import os
import tempfile
from pathlib import Path
from agent_bridge.config import find_project_root, load_all_configs
from agent_bridge.runs import setup_agent_directories

def cmd_doctor(args):
    """
    Executes 'agent-bridge doctor' diagnostics.
    """
    print("==================================================")
    print("Agent Bridge Doctor - Diagnostic Utility")
    print("==================================================")
    
    passed_all = True
    
    # 1. Python Version Check
    py_version = sys.version_info
    print(f"[*] Python Version: {sys.version} ... ", end="")
    if py_version.major == 3 and py_version.minor >= 12:
        print("[OK]")
    else:
        print("[FAIL] (Requires Python >= 3.12)")
        passed_all = False
        
    # 2. Project Root Detection
    root = find_project_root()
    print(f"[*] Project Root: {root} ... [OK]")
    
    # 3. Canonical Plan & Roadmap files check
    plan_file = root / "docs" / "plan" / "agent_bridge_mvp.md"
    roadmap_file = root / "docs" / "plan" / "roadmap.md"
    
    print(f"[*] Canonical Plan (docs/plan/agent_bridge_mvp.md): ", end="")
    if plan_file.exists():
        print("[OK]")
    else:
        print("[FAIL] (Missing in root)")
        passed_all = False
        
    print(f"[*] Roadmap (docs/plan/roadmap.md): ", end="")
    if roadmap_file.exists():
        print("[OK]")
    else:
        print("[FAIL] (Missing in root)")
        passed_all = False
        
    # Ensure directories are set up prior to verification
    setup_agent_directories(root)
    
    # 4. Required Directories Check
    req_dirs = [
        Path("config"),
        Path("src") / "agent_bridge",
        Path(".agent") / "tasks",
        Path(".agent") / "runs",
        Path(".agent") / "reports",
        Path(".agent") / "metrics",
        Path(".agent") / "sessions",
    ]
    
    print("[*] Required Directories:")
    for d in req_dirs:
        full_path = root / d
        print(f"    - {d} : ", end="")
        if full_path.exists():
            print("[OK]")
        else:
            print("[FAIL] (Directory does not exist)")
            passed_all = False
            
    # 5. Required Config Files Check
    req_configs = [
        Path("config") / "agents.toml",
        Path("config") / "runners.toml",
        Path("config") / "providers.toml",
    ]
    
    print("[*] Required Config Files:")
    for f in req_configs:
        full_path = root / f
        print(f"    - {f} : ", end="")
        if full_path.exists():
            print("[OK]")
        else:
            print("[FAIL] (File does not exist)")
            passed_all = False
            
    # 6. Writable .agent/runs Check
    runs_dir = root / ".agent" / "runs"
    print(f"[*] Writable .agent/runs directory: ", end="")
    if runs_dir.exists():
        try:
            # Try to write a temp file
            temp_fd, temp_path = tempfile.mkstemp(dir=runs_dir)
            try:
                with os.fdopen(temp_fd, 'w') as temp_file:
                    temp_file.write("test")
            finally:
                os.remove(temp_path)
            print("[OK]")
        except Exception as e:
            print(f"[FAIL] (Cannot write to directory: {e})")
            passed_all = False
    else:
        print("[FAIL] (Directory does not exist)")
        passed_all = False
        
    # 7. Check if configs load properly
    print("[*] Loading configurations... ", end="")
    try:
        configs = load_all_configs(root)
        print("[OK]")
        agents = configs.get("agents", {}).get("agents", {})
        if agents:
            print("    Configured Agents:")
            for agent_name, agent_conf in agents.items():
                print(f"      - {agent_name} ({agent_conf.get('model', 'unknown model')})")
        else:
            print("    (No agents configured in config/agents.toml)")
    except Exception as e:
        print(f"[FAIL] (Error loading config: {e})")
        passed_all = False
        
    print("==================================================")
    if passed_all:
        print("Doctor status: ALL CHECKS PASSED!")
        sys.exit(0)
    else:
        print("Doctor status: SOME CHECKS FAILED. Please resolve issues above.")
        sys.exit(1)

def cmd_run(args):
    """
    Executes 'agent-bridge run --agent <agent> --task <task> --workspace <workspace>'
    """
    from agent_bridge.runs import execute_mock_run
    
    agent_name = args.agent
    task_path = Path(args.task)
    workspace_path = Path(args.workspace)
    
    print(f"[*] Starting run delegation lifecycle (Mock Stage)...")
    print(f"    - Agent: {agent_name}")
    print(f"    - Task: {task_path}")
    print(f"    - Workspace: {workspace_path}")
    
    try:
        run_id = execute_mock_run(agent_name, task_path, workspace_path)
        print(f"[OK] Run '{run_id}' completed (Mock / Blocked status).")
        print(f"     Artifacts generated under .agent/runs/{run_id}/")
        sys.exit(0)
    except Exception as e:
        print(f"[FAIL] Run failed: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_summarize(args):
    """
    Executes 'agent-bridge summarize --run <run_id_or_latest>'
    """
    from agent_bridge.config import find_project_root
    from agent_bridge.runs import find_latest_run
    import json
    
    root = find_project_root()
    run_arg = args.run
    
    try:
        if run_arg == "latest":
            run_dir = find_latest_run(root)
        else:
            run_dir = root / ".agent" / "runs" / run_arg
            if not run_dir.exists() or not run_dir.is_dir():
                raise FileNotFoundError(f"Run directory for '{run_arg}' does not exist")
    except Exception as e:
        print(f"[FAIL] Error resolving run: {e}", file=sys.stderr)
        sys.exit(1)
        
    run_id = run_dir.name
    
    summary_path = run_dir / "summary.md"
    report_path = run_dir / "decision_report.json"
    
    if not summary_path.exists():
        print(f"[FAIL] Missing required run artifact: {summary_path.name} in {run_id}", file=sys.stderr)
        sys.exit(1)
        
    if not report_path.exists():
        print(f"[FAIL] Missing required run artifact: {report_path.name} in {run_id}", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            report_data = json.load(f)
            
        with open(summary_path, "r", encoding="utf-8") as f:
            summary_text = f.read()
            
    except Exception as e:
        print(f"[FAIL] Error reading artifacts for run '{run_id}': {e}", file=sys.stderr)
        sys.exit(1)
        
    print("==================================================")
    print(f"Agent Bridge Run Summary - {run_id}")
    print("==================================================")
    print(f"Agent   : {report_data.get('agent', 'unknown')}")
    print(f"Model   : {report_data.get('model', 'unknown')}")
    print(f"Status  : {report_data.get('status', 'unknown').upper()}")
    print(f"Verdict : {report_data.get('verdict', 'unknown')}")
    print("--------------------------------------------------")
    
    summary_line = report_data.get("summary", "")
    print(f"Executive Summary:")
    print(f"  {summary_line}")
    print("--------------------------------------------------")
    
    risks = report_data.get("risks", [])
    if risks:
        print("Key Risks Identified:")
        for r in risks:
            print(f"  - {r}")
    else:
        print("Key Risks Identified: None")
        
    questions = report_data.get("open_questions", [])
    if questions:
        print("Open Questions:")
        for q in questions:
            print(f"  - {q}")
            
    next_action = report_data.get("next_action", "")
    if next_action:
        print("--------------------------------------------------")
        print(f"Next Recommended Action:")
        print(f"  {next_action}")
        
    print("==================================================")
    sys.exit(0)

def cmd_compare(args):
    print(f"Mock Compare requested: runs={args.runs}")
    print("Compare functionality is not implemented in Phase 0.")
    sys.exit(0)

def cmd_eval(args):
    """
    Executes 'agent-bridge eval --run <run_id_or_latest>' to evaluate an agent run.
    Supports both interactive and non-interactive configurations.
    """
    from agent_bridge.config import find_project_root
    from agent_bridge.runs import find_latest_run, write_json
    from agent_bridge.contracts import validate_decision_report
    from agent_bridge.evaluator import calculate_quality_score, update_model_routing_memory, ERROR_TAXONOMY
    import json
    
    root = find_project_root()
    run_arg = args.run
    
    # 1. Resolve run directory
    try:
        if run_arg == "latest":
            run_dir = find_latest_run(root)
        else:
            run_dir = root / ".agent" / "runs" / run_arg
            if not run_dir.exists() or not run_dir.is_dir():
                raise FileNotFoundError(f"Run directory for '{run_arg}' does not exist")
    except Exception as e:
        print(f"[FAIL] Error resolving run: {e}", file=sys.stderr)
        sys.exit(1)
        
    run_id = run_dir.name
    report_path = run_dir / "decision_report.json"
    metrics_path = run_dir / "metrics.json"
    
    if not report_path.exists():
        print(f"[FAIL] Missing required run artifact: decision_report.json in {run_id}", file=sys.stderr)
        sys.exit(1)
        
    if not metrics_path.exists():
        print(f"[FAIL] Missing required run artifact: metrics.json in {run_id}", file=sys.stderr)
        sys.exit(1)
        
    # 2. Check if interactive mode is explicitly requested
    is_interactive = getattr(args, "interactive", False)
        
    if not is_interactive:
        # Non-interactive Mode
        if args.level is not None:
            acceptance_level = args.level
            accepted = acceptance_level in ["full", "partial"]
        else:
            accepted = args.accepted
            acceptance_level = "full" if accepted else "none"
        
        errors_str = args.errors if args.errors else "none"
        error_categories = [e.strip() for e in errors_str.split(",") if e.strip()]
        if not error_categories:
            error_categories = ["none"]
            
        best_use_case = args.best_use if args.best_use else ""
        avoid_for = args.avoid if args.avoid else ""
        notes = args.notes if args.notes else "Evaluated via CLI arguments."
    else:
        # Interactive Mode
        print("==================================================")
        print(f"Interactive Run Evaluation - {run_id}")
        print("==================================================")
        
        try:
            # Question 1: Accepted?
            while True:
                ans = input("Is the run accepted? (y/n): ").strip().lower()
                if ans in ["y", "yes", "n", "no"]:
                    accepted = ans in ["y", "yes"]
                    break
                print("[!] Please enter 'y' or 'n'.")
                
            # Question 2: Acceptance level?
            default_level = "full" if accepted else "none"
            while True:
                level_ans = input(f"Acceptance level (none, partial, full) [{default_level}]: ").strip().lower()
                if not level_ans:
                    acceptance_level = default_level
                    break
                if level_ans in ["none", "partial", "full"]:
                    acceptance_level = level_ans
                    # Keep accepted aligned
                    accepted = acceptance_level in ["full", "partial"]
                    break
                print("[!] Please enter 'none', 'partial', or 'full'.")
                
            # Question 3: Error categories?
            print("\nAllowed error categories:")
            print(", ".join(ERROR_TAXONOMY))
            while True:
                errors_ans = input("Select error categories (comma-separated, or 'none') [none]: ").strip()
                if not errors_ans:
                    error_categories = ["none"]
                    break
                cats = [e.strip().lower() for e in errors_ans.split(",") if e.strip()]
                # Validate all entered categories
                invalid_cats = [c for c in cats if c not in ERROR_TAXONOMY]
                if invalid_cats:
                    print(f"[!] Invalid categories detected: {invalid_cats}. Please try again.")
                    continue
                error_categories = cats
                break
                
            # Question 4: Best use case?
            best_use_case = input("\nBest use case for this agent/model? (e.g. bug investigation): ").strip()
            
            # Question 5: Avoid for?
            avoid_for = input("What to avoid for this agent/model? (e.g. large refactors): ").strip()
            
            # Question 6: Notes?
            notes = input("Commander notes/feedback: ").strip()
            if not notes:
                notes = "Evaluated interactively by commander."
                
        except (KeyboardInterrupt, EOFError):
            print("\n[!] Interactive evaluation cancelled.")
            sys.exit(1)
            
    # 3. Validate values
    invalid_cats = [c for c in error_categories if c not in ERROR_TAXONOMY]
    if invalid_cats:
        print(f"[FAIL] Invalid error categories: {invalid_cats}", file=sys.stderr)
        print(f"       Must be one of: {ERROR_TAXONOMY}", file=sys.stderr)
        sys.exit(1)
        
    if acceptance_level not in ["none", "partial", "full"]:
        print(f"[FAIL] Invalid acceptance level: '{acceptance_level}'", file=sys.stderr)
        sys.exit(1)
        
    # 4. Calculate Score
    score = calculate_quality_score(error_categories)
    
    # 5. Create verdict.json
    verdict_data = {
        "accepted": accepted,
        "acceptance_level": acceptance_level,
        "error_categories": error_categories,
        "score": score,
        "best_use_case": best_use_case,
        "avoid_for": avoid_for,
        "notes": notes
    }
    write_json(run_dir / "verdict.json", verdict_data)
    
    # 6. Update decision_report.json
    if getattr(args, "write_report_verdict", False):
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                report_dict = json.load(f)
                
            # Map acceptance level to decision_report verdict enum
            # full -> PASS, partial -> NEEDS_DECISION, none -> FIX_REQUIRED
            if acceptance_level == "full":
                verdict_val = "PASS"
            elif acceptance_level == "partial":
                verdict_val = "NEEDS_DECISION"
            else:
                verdict_val = "FIX_REQUIRED"
                
            report_dict["verdict"] = verdict_val
            validate_decision_report(report_dict)
            write_json(report_path, report_dict)
        except Exception as e:
            print(f"[FAIL] Failed to update decision_report.json: {e}", file=sys.stderr)
            sys.exit(1)
        
    # 7. Update metrics.json
    try:
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics_dict = json.load(f)
        metrics_dict["commander_verdict"] = verdict_data
        write_json(metrics_path, metrics_dict)
    except Exception as e:
        print(f"[FAIL] Failed to update metrics.json: {e}", file=sys.stderr)
        sys.exit(1)
        
    # 8. Dynamic aggregation of routing notes
    try:
        update_model_routing_memory(root)
    except Exception as e:
        print(f"[WARNING] Failed to update model routing memory: {e}", file=sys.stderr)
        
    print("--------------------------------------------------")
    print(f"[OK] Evaluation successfully recorded for run '{run_id}'.")
    print(f"     Calculated Quality Score: {score}")
    print(f"     Recorded Verdict        : {'PASS' if accepted and acceptance_level == 'full' else ('NEEDS_DECISION' if accepted else 'FIX_REQUIRED')}")
    print("==================================================")
    sys.exit(0)

def cmd_task_validate(args):
    """
    Executes 'agent-bridge task validate --spec <spec.toml>'.
    """
    from agent_bridge.task_spec import load_task_spec, validate_task_spec

    spec_path = Path(args.spec)
    try:
        result = validate_task_spec(load_task_spec(spec_path))
    except Exception as e:
        print(f"[FAIL] Task spec validation failed: {e}", file=sys.stderr)
        sys.exit(1)

    spec = result.spec
    print("==================================================")
    print("Agent Bridge Task Spec Validation")
    print("==================================================")
    print(f"Spec    : {spec_path}")
    print(f"Task ID : {spec.get('task_id')}")
    print(f"Phase   : {spec.get('phase')}")
    print(f"Slice   : {spec.get('slice')}")
    print(f"Title   : {spec.get('title')}")
    print(f"Allowed : {len(spec.get('allowed_files', []))} file patterns")
    if "read_scope" in spec:
        print(f"Read    : {len(spec.get('read_scope', []))} file patterns")
    if "write_scope" in spec:
        print(f"Write   : {len(spec.get('write_scope', []))} file patterns")
    print(f"Forbidden: {len(spec.get('forbidden_files', []))} file patterns")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"  - {warning}")
    print("==================================================")
    print("[OK] task_spec.v0 validation passed")
    sys.exit(0)

def cmd_task_render(args):
    """
    Executes 'agent-bridge task render --spec <spec.toml> --out <task.md>'.
    """
    from agent_bridge.task_spec import write_rendered_task

    spec_path = Path(args.spec)
    out_path = Path(args.out)
    try:
        write_rendered_task(spec_path, out_path)
    except Exception as e:
        print(f"[FAIL] Task spec render failed: {e}", file=sys.stderr)
        sys.exit(1)

    print("==================================================")
    print("Agent Bridge Task Spec Render")
    print("==================================================")
    print(f"Spec   : {spec_path}")
    print(f"Output : {out_path}")
    print("==================================================")
    print("[OK] rendered task prompt written")
    sys.exit(0)

def cmd_task_check_result(args):
    """
    Executes 'agent-bridge task check-result --spec <spec.toml> --workspace <path>'.
    """
    from agent_bridge.task_spec import check_task_result, load_task_spec

    spec_path = Path(args.spec)
    workspace_path = Path(args.workspace)
    try:
        result = check_task_result(load_task_spec(spec_path), workspace_path)
    except Exception as e:
        print(f"[FAIL] Task result check failed: {e}", file=sys.stderr)
        sys.exit(1)

    print("==================================================")
    print("Agent Bridge Task Result Check")
    print("==================================================")
    print(f"Spec      : {spec_path}")
    print(f"Workspace : {workspace_path}")
    print(f"Changed   : {len(result.changed_files)} files")
    if result.changed_files:
        print("Changed files:")
        for path in result.changed_files:
            print(f"  - {path}")
    if result.forbidden_matches:
        print("Forbidden file violations:")
        for path in result.forbidden_matches:
            print(f"  - {path}")
    if result.out_of_scope_files:
        print("Out-of-scope file violations:")
        for path in result.out_of_scope_files:
            print(f"  - {path}")
    print("==================================================")
    if result.passed:
        print("[OK] task result stayed within allowed scope")
        sys.exit(0)
    print("[FAIL] task result exceeded task_spec.v0 scope", file=sys.stderr)
    sys.exit(1)

def cmd_task_check_tool_use(args):
    """
    Executes 'agent-bridge task check-tool-use --spec <spec.toml> --run <run> --workspace <path>'.
    """
    from agent_bridge.config import find_project_root
    from agent_bridge.runs import find_latest_run
    from agent_bridge.task_spec import check_run_tool_use, load_task_spec

    root = find_project_root()
    spec_path = Path(args.spec)
    workspace_path = Path(args.workspace)
    try:
        if args.run == "latest":
            run_dir = find_latest_run(root)
        else:
            run_dir = root / ".agent" / "runs" / args.run
            if not run_dir.exists() or not run_dir.is_dir():
                raise FileNotFoundError(f"Run directory for '{args.run}' does not exist")
        result = check_run_tool_use(load_task_spec(spec_path), run_dir, workspace_path)
    except Exception as e:
        print(f"[FAIL] Tool-use check failed: {e}", file=sys.stderr)
        sys.exit(1)

    print("==================================================")
    print("Agent Bridge Tool-Use Scope Check")
    print("==================================================")
    print(f"Spec      : {spec_path}")
    print(f"Run       : {run_dir.name}")
    print(f"Workspace : {workspace_path}")
    print(f"Tool uses : {len(result.tool_uses)}")
    if result.tool_uses:
        print("Observed tools:")
        for item in result.tool_uses:
            tool = item.get("tool") or "unknown"
            status = item.get("status") or "unknown"
            print(f"  - {tool} ({status})")
    if result.write_tool_uses:
        print("Write-capable tool violations:")
        for tool in result.write_tool_uses:
            print(f"  - {tool}")
    if result.forbidden_matches:
        print("Forbidden path violations:")
        for path in result.forbidden_matches:
            print(f"  - {path}")
    if result.out_of_scope_paths:
        print("Out-of-scope path violations:")
        for path in result.out_of_scope_paths:
            print(f"  - {path}")
    if result.outside_workspace_paths:
        print("Outside-workspace path violations:")
        for path in result.outside_workspace_paths:
            print(f"  - {path}")
    print("==================================================")
    if result.passed:
        print("[OK] tool-use paths stayed within task_spec.v0 scope")
        sys.exit(0)
    print("[FAIL] tool-use paths exceeded task_spec.v0 scope", file=sys.stderr)
    sys.exit(1)

def cmd_task_gate(args):
    """
    Executes the standard post-run gate for delegated tasks.
    """
    from agent_bridge.config import find_project_root
    from agent_bridge.runs import find_latest_run
    from agent_bridge.task_spec import check_run_artifacts, check_run_tool_use, load_task_spec
    import json

    root = find_project_root()
    spec_path = Path(args.spec)
    workspace_path = Path(args.workspace)
    try:
        if args.run == "latest":
            run_dir = find_latest_run(root)
        else:
            run_dir = root / ".agent" / "runs" / args.run
            if not run_dir.exists() or not run_dir.is_dir():
                raise FileNotFoundError(f"Run directory for '{args.run}' does not exist")

        report_path = run_dir / "decision_report.json"
        if not report_path.exists():
            raise FileNotFoundError(f"Missing required run artifact: {report_path}")
        with report_path.open("r", encoding="utf-8") as f:
            report = json.load(f)
        status = str(report.get("status") or "")
        if status != "completed":
            raise ValueError(f"Run status is not completed: {status}")

        spec = load_task_spec(spec_path)
        artifact_result = check_run_artifacts(spec, run_dir)
        tool_result = check_run_tool_use(spec, run_dir, workspace_path)
    except Exception as e:
        print(f"[FAIL] Task gate failed: {e}", file=sys.stderr)
        sys.exit(1)

    print("==================================================")
    print("Agent Bridge Task Gate")
    print("==================================================")
    print(f"Spec      : {spec_path}")
    print(f"Run       : {run_dir.name}")
    print(f"Workspace : {workspace_path}")
    print(f"Status    : {status}")
    print(f"Artifacts : {len(artifact_result.expected_artifacts)} expected")
    if artifact_result.missing_artifacts:
        print("Missing artifacts:")
        for path in artifact_result.missing_artifacts:
            print(f"  - {path}")
    print(f"Tool uses : {len(tool_result.tool_uses)}")
    if tool_result.write_tool_uses:
        print("Write-capable tool violations:")
        for tool in tool_result.write_tool_uses:
            print(f"  - {tool}")
    if tool_result.forbidden_matches:
        print("Forbidden path violations:")
        for path in tool_result.forbidden_matches:
            print(f"  - {path}")
    if tool_result.out_of_scope_paths:
        print("Out-of-scope path violations:")
        for path in tool_result.out_of_scope_paths:
            print(f"  - {path}")
    if tool_result.outside_workspace_paths:
        print("Outside-workspace path violations:")
        for path in tool_result.outside_workspace_paths:
            print(f"  - {path}")
    print("==================================================")
    if artifact_result.passed and tool_result.passed:
        print("[OK] task gate passed")
        sys.exit(0)
    print("[FAIL] task gate rejected run", file=sys.stderr)
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        prog="agent-bridge",
        description="Agent Bridge: A CLI-first control plane for agent delegation"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")
    
    # 1. doctor
    subparsers.add_parser("doctor", help="Run system and workspace diagnostics")
    
    # 2. run
    parser_run = subparsers.add_parser("run", help="Delegate a task to an agent")
    parser_run.add_argument("--agent", required=True, help="Agent identifier (e.g. glm_review)")
    parser_run.add_argument("--task", required=True, help="Path to the task file (.md)")
    parser_run.add_argument("--workspace", required=True, help="Path to the target workspace")
    
    # 3. summarize
    parser_sum = subparsers.add_parser("summarize", help="Summarize agent run output")
    parser_sum.add_argument("--run", default="latest", help="Run ID to summarize (default: latest)")
    
    # 4. compare
    parser_comp = subparsers.add_parser("compare", help="Compare two agent runs")
    parser_comp.add_argument("--runs", nargs=2, required=True, metavar=("RUN_A", "RUN_B"), help="Two Run IDs to compare")
    
    # 5. eval
    parser_eval = subparsers.add_parser("eval", help="Evaluate an agent run")
    parser_eval.add_argument("--run", default="latest", help="Run ID to evaluate (default: latest)")
    parser_eval.add_argument("--accepted", action="store_true", help="Mark run as accepted")
    parser_eval.add_argument("--level", choices=["none", "partial", "full"], help="Set acceptance level")
    parser_eval.add_argument("--errors", help="Comma-separated list of error categories")
    parser_eval.add_argument("--best-use", help="Best use case description")
    parser_eval.add_argument("--avoid", help="Avoid for description")
    parser_eval.add_argument("--notes", help="Commander feedback/notes")
    parser_eval.add_argument("--interactive", action="store_true", help="Run in interactive mode with prompts")
    parser_eval.add_argument("--write-report-verdict", action="store_true", help="Write evaluation verdict back to decision_report.json")

    # 6. task
    parser_task = subparsers.add_parser("task", help="Validate and render task specs")
    task_subparsers = parser_task.add_subparsers(dest="task_command", help="Task subcommand")

    parser_task_validate = task_subparsers.add_parser("validate", help="Validate task_spec.v0 TOML")
    parser_task_validate.add_argument("--spec", required=True, help="Path to task_spec.v0 TOML")

    parser_task_render = task_subparsers.add_parser("render", help="Render task_spec.v0 TOML to Markdown")
    parser_task_render.add_argument("--spec", required=True, help="Path to task_spec.v0 TOML")
    parser_task_render.add_argument("--out", required=True, help="Path to output Markdown task")

    parser_task_check = task_subparsers.add_parser("check-result", help="Check git changes against task_spec.v0 scope")
    parser_task_check.add_argument("--spec", required=True, help="Path to task_spec.v0 TOML")
    parser_task_check.add_argument("--workspace", default=".", help="Workspace path to inspect with git status")

    parser_task_tool_use = task_subparsers.add_parser("check-tool-use", help="Check raw run tool-use paths against task_spec.v0 scope")
    parser_task_tool_use.add_argument("--spec", required=True, help="Path to task_spec.v0 TOML")
    parser_task_tool_use.add_argument("--run", default="latest", help="Run ID to inspect (default: latest)")
    parser_task_tool_use.add_argument("--workspace", default=".", help="Workspace path used to normalize tool paths")

    parser_task_gate = task_subparsers.add_parser("gate", help="Run the standard post-run task gate")
    parser_task_gate.add_argument("--spec", required=True, help="Path to task_spec.v0 TOML")
    parser_task_gate.add_argument("--run", default="latest", help="Run ID to inspect (default: latest)")
    parser_task_gate.add_argument("--workspace", default=".", help="Workspace path used to normalize tool paths")
    
    args = parser.parse_args()
    
    if args.command == "doctor":
        cmd_doctor(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "summarize":
        cmd_summarize(args)
    elif args.command == "compare":
        cmd_compare(args)
    elif args.command == "eval":
        cmd_eval(args)
    elif args.command == "task":
        if args.task_command == "validate":
            cmd_task_validate(args)
        elif args.task_command == "render":
            cmd_task_render(args)
        elif args.task_command == "check-result":
            cmd_task_check_result(args)
        elif args.task_command == "check-tool-use":
            cmd_task_check_tool_use(args)
        elif args.task_command == "gate":
            cmd_task_gate(args)
        else:
            parser_task.print_help()
            sys.exit(0)
    else:
        parser.print_help()
        sys.exit(0)

if __name__ == "__main__":
    main()
