import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "adapter.v0.1"
SMOKE_TOKEN = "AGENT_BRIDGE_ANTIGRAVITY_SMOKE_OK"


def main() -> int:
    # Read stdin once and cache
    raw = sys.stdin.buffer.read()
    request_id = ""
    try:
        request = json.loads(raw.decode("utf-8"))
        request_id = request.get("request_id", "")
        _emit_event(request_id, "progress", "antigravity smoke adapter started")
        result = _run_antigravity(request)
        _emit_response(request_id, result)
        return 0
    except Exception as exc:
        _emit_response(
            request_id,
            {
                "ok": False,
                "run_status": "failed",
                "summary": f"Antigravity smoke adapter failed: {exc}",
                "artifacts": [],
                "metrics": {},
                "error": {"code": "adapter_error", "message": str(exc)},
            },
        )
        return 1


def _run_antigravity(request: dict[str, Any]) -> dict[str, Any]:
    payload = request.get("payload") or {}
    context = request.get("context") or {}
    constraints = context.get("constraints") or {}
    workspace_path = payload.get("workspace_path") or _first_filesystem_scope(constraints)
    if not workspace_path:
        raise ValueError("workspace_path is required")

    workspace = Path(workspace_path)
    if not workspace.exists() or not workspace.is_dir():
        raise ValueError(f"workspace_path is not a directory: {workspace}")

    # Load configuration.
    cmd_name = os.environ.get("AGENT_BRIDGE_ANTIGRAVITY_COMMAND", "agy").strip()
    timeout_ms = int(os.environ.get("AGENT_BRIDGE_ANTIGRAVITY_TIMEOUT_MS", "60000"))
    print_timeout = os.environ.get("AGENT_BRIDGE_ANTIGRAVITY_PRINT_TIMEOUT", "60s").strip()
    direct_smoke = os.environ.get("AGENT_BRIDGE_ANTIGRAVITY_DIRECT_SMOKE", "").strip().lower() in {"1", "true", "yes"}
    output_format = os.environ.get("AGENT_BRIDGE_ANTIGRAVITY_FORMAT", "text").strip().lower()
    session_policy = os.environ.get("AGENT_BRIDGE_ANTIGRAVITY_SESSION_POLICY", "new").strip() or "new"
    session_name = os.environ.get("AGENT_BRIDGE_ANTIGRAVITY_SESSION_NAME", "").strip() or "default"
    explicit_session_id = os.environ.get("AGENT_BRIDGE_ANTIGRAVITY_SESSION_ID", "").strip()

    session_id = _resolve_session_id(workspace, session_policy, session_name, explicit_session_id)
    session_reused = bool(session_id)

    task_prompt = str(payload.get("task_prompt") or "")
    
    XML_GUIDELINE = (
        "\n\n[CRITICAL REQUIREMENT - XML REPORT FORMAT]\n"
        "You must record your final report in XML format inside the scratch directory. "
        "Create a file named 'response.xml' or similar in the scratch directory. "
        "The file content must be wrapped in an <agent_report> root element. "
        "Do not use markdown blocks (e.g. ```xml) around the XML file content itself. "
        "Inside the XML, include the following tags exactly:\n"
        "<agent_report version=\"agent-bridge.report.v0\">\n"
        "  <status>completed or failed</status>\n"
        "  <summary>A concise summary containing AGENT_BRIDGE_ANTIGRAVITY_SMOKE_OK</summary>\n"
        "  <files_inspected>\n"
        "    <file>path/to/inspected/file</file>\n"
        "  </files_inspected>\n"
        "  <files_changed>\n"
        "    <file>path/to/changed/file</file>\n"
        "  </files_changed>\n"
        "  <commands_run>\n"
        "    <command>run command</command>\n"
        "  </commands_run>\n"
        "  <risks>\n"
        "    <risk>identified risk</risk>\n"
        "  </risks>\n"
        "  <open_questions>\n"
        "    <question>open question</question>\n"
        "  </open_questions>\n"
        "  <next_step>next step</next_step>\n"
        "</agent_report>\n"
        "Use <![CDATA[...]]> for any values containing special XML characters to prevent syntax breakdown."
    )

    if direct_smoke:
        if session_reused:
            message = (
                "You are running in non-interactive print mode. Do not use tools. "
                "Do not inspect files. Reply with only the exact smoke token from the previous turn."
            )
        else:
            message = (
                "You are running in non-interactive print mode. Do not use tools. "
                "Do not inspect files. Reply with exactly this single line: "
                f"{SMOKE_TOKEN}"
            )
    else:
        message = task_prompt or f"Remember this smoke token for the next turn: {SMOKE_TOKEN}. Reply with exactly: {SMOKE_TOKEN}"
        if output_format == "xml":
            message += XML_GUIDELINE

    log_path = _new_temp_log_path()

    # Smoke only: this flag avoids permission prompts in background runs, but it is not
    # acceptable for production write-capable delegation.
    cmd = [
        cmd_name,
        "--dangerously-skip-permissions",
        "--log-file",
        str(log_path),
        "--print-timeout",
        print_timeout,
        "--print",
    ]
    if session_id:
        cmd.extend(["--conversation", session_id])
    cmd.append(message)

    before_sessions = _scan_project_markers(workspace) | _scan_global_conversations()
    before_scratch = _scan_scratch_files()
    started = time.time()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=False,
        timeout=timeout_ms / 1000.0,
        shell=False,
        input=b"",
    )
    elapsed_ms = int((time.time() - started) * 1000)
    after_sessions = _scan_project_markers(workspace) | _scan_global_conversations()
    after_scratch = _scan_scratch_files()

    new_sessions = after_sessions - before_sessions
    log_text = _read_text(log_path, limit=24_000)
    log_session_id = _extract_conversation_id(log_text)
    observed_session_id = sorted(new_sessions)[-1] if new_sessions else log_session_id or session_id

    if observed_session_id and session_policy == "continue_named":
        _write_session_state(workspace, session_name, observed_session_id)

    stdout = _decode_process_output(result.stdout)
    stderr = _decode_process_output(result.stderr)
    scratch_text = _read_new_scratch_text(before_scratch, after_scratch)

    # Attempt to parse XML report
    xml_data = _try_parse_xml_report(scratch_text)

    if xml_data:
        xml_summary = xml_data.get("summary", "")
        xml_status = xml_data.get("status", "").strip().lower()
        status_ok = xml_status == "completed"
        missing_smoke_token = SMOKE_TOKEN not in xml_summary

        ok = result.returncode == 0 and status_ok and not missing_smoke_token
        summary = f"Antigravity smoke exited {result.returncode} with XML report."
        if xml_summary:
            summary += f" Response: {xml_summary.replace('\n', ' ')[:240]}"
        if not status_ok:
            summary = f"Antigravity XML report status was not completed: {xml_status}."
        elif missing_smoke_token:
            summary = f"Antigravity XML report did not include required smoke token {SMOKE_TOKEN}."
            
        combined_output = xml_summary
    else:
        combined_output = "\n".join(part for part in (stdout, scratch_text) if part.strip())
        empty_output = not stdout.strip() and not stderr.strip()
        missing_smoke_token = direct_smoke and (SMOKE_TOKEN not in combined_output)

        ok = result.returncode == 0 and bool(combined_output.strip()) and not missing_smoke_token
        summary = f"Antigravity smoke exited {result.returncode}."
        if combined_output.strip():
            summary += f" Response: {combined_output.strip().replace('\n', ' ')[:240]}"

        if empty_output and not scratch_text.strip():
            summary = "Antigravity exited but produced no stdout, stderr, or readable scratch output."
        elif missing_smoke_token:
            summary = f"Antigravity output did not include required smoke token {SMOKE_TOKEN}."

    run_artifacts = [
        {
            "kind": "stdout_preview",
            "text": stdout,
        },
        {
            "kind": "stderr_preview",
            "text": stderr,
        },
        {
            "kind": "antigravity_log_preview",
            "text": log_text,
        },
        {
            "kind": "antigravity_scratch_preview",
            "text": scratch_text,
        },
    ]
    if xml_data:
        run_artifacts.append({
            "kind": "xml_report_parsed",
            "text": json.dumps(xml_data, indent=2, ensure_ascii=False),
        })
        run_artifacts.append({
            "kind": "xml_report_raw",
            "text": scratch_text,
        })

    return {
        "ok": ok,
        "run_status": "completed" if ok else "failed",
        "summary": summary,
        "artifacts": run_artifacts,
        "metrics": {
            "elapsed_ms": elapsed_ms,
            "cost_usd": 0.0,
            "tokens_in": None,
            "tokens_out": None,
            "session_id": observed_session_id,
            "session_reused": session_reused,
            "session_policy": session_policy,
            "session_name": session_name,
            "log_path": str(log_path),
        },
        "error": None if ok else {"code": "antigravity_failed", "message": stderr or summary},
    }


def _first_filesystem_scope(constraints: dict[str, Any]) -> str:
    scope = constraints.get("filesystem_scope") or []
    if isinstance(scope, list) and scope:
        return str(scope[0])
    return ""


def _decode_process_output(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.decode("utf-8", errors="replace")


def _try_parse_xml_report(text: str) -> dict[str, Any] | None:
    if not text or "<agent_report" not in text:
        return None

    clean_text = text.strip()
    if clean_text.startswith("```"):
        clean_text = re.sub(r"^```[a-zA-Z]*\n", "", clean_text)
        clean_text = re.sub(r"\n```$", "", clean_text)
        clean_text = clean_text.strip()

    def extract_tag_content(tag_name: str, default: str = "") -> str:
        pattern = rf"<{tag_name}(?:\s+[^>]*)?>(?:<!\[CDATA\[(.*?)\]\]>|([^<]*))</{tag_name}>"
        match = re.search(pattern, clean_text, re.DOTALL)
        if match:
            cdata, plain = match.groups()
            return (cdata if cdata is not None else plain or "").strip()

        fallback_pattern = rf"<{tag_name}(?:\s+[^>]*)?>(?:<!\[CDATA\[(.*?)\]\]>|([^<]*))"
        match = re.search(fallback_pattern, clean_text, re.DOTALL)
        if match:
            cdata, plain = match.groups()
            val = (cdata if cdata is not None else plain or "").strip()
            if "<" in val:
                val = val.split("<")[0].strip()
            return val
        return default

    def extract_list_tag_content(parent_tag: str, child_tag: str) -> list[str]:
        parent_pattern = rf"<{parent_tag}(?:\s+[^>]*)?>(.*?)</{parent_tag}>"
        parent_match = re.search(parent_pattern, clean_text, re.DOTALL)
        content_area = parent_match.group(1) if parent_match else clean_text

        child_pattern = rf"<{child_tag}(?:\s+[^>]*)?>(?:<!\[CDATA\[(.*?)\]\]>|([^<]*))</{child_tag}>"
        items = re.findall(child_pattern, content_area, re.DOTALL)
        results = []
        for cdata, plain in items:
            results.append((cdata if cdata else plain or "").strip())
        return results

    try:
        status = extract_tag_content("status")
        summary = extract_tag_content("summary")
        next_step = extract_tag_content("next_step")

        if not status and not summary:
            return None

        files_inspected = extract_list_tag_content("files_inspected", "file")
        files_changed = extract_list_tag_content("files_changed", "file")
        commands_run = extract_list_tag_content("commands_run", "command")
        risks = extract_list_tag_content("risks", "risk")
        open_questions = extract_list_tag_content("open_questions", "question")

        return {
            "status": status,
            "summary": summary,
            "files_inspected": files_inspected,
            "files_changed": files_changed,
            "commands_run": commands_run,
            "risks": risks,
            "open_questions": open_questions,
            "next_step": next_step
        }
    except Exception:
        return None


def _new_temp_log_path() -> Path:
    fd, name = tempfile.mkstemp(prefix="agent_bridge_antigravity_", suffix=".log")
    os.close(fd)
    return Path(name)


def _scan_project_markers(workspace: Path) -> set[str]:
    return _scan_json_stems(workspace / ".antigravitycli")


def _scan_global_conversations() -> set[str]:
    return _scan_file_stems(Path.home() / ".gemini" / "antigravity-cli" / "conversations", ".pb")


def _scan_json_stems(path: Path) -> set[str]:
    return _scan_file_stems(path, ".json")


def _scan_file_stems(path: Path, suffix: str) -> set[str]:
    if not path.exists() or not path.is_dir():
        return set()
    try:
        return {f.stem for f in path.iterdir() if f.is_file() and f.suffix == suffix}
    except Exception:
        return set()


def _scan_scratch_files() -> dict[Path, float]:
    scratch = Path.home() / ".gemini" / "antigravity-cli" / "scratch"
    if not scratch.exists() or not scratch.is_dir():
        return {}
    found: dict[Path, float] = {}
    try:
        for path in scratch.iterdir():
            if path.is_file():
                found[path] = path.stat().st_mtime
    except Exception:
        return {}
    return found


def _read_new_scratch_text(before: dict[Path, float], after: dict[Path, float]) -> str:
    # 1. Primary: Detect newly created or explicitly modified files
    changed = [
        path for path, mtime in after.items()
        if path not in before or mtime > before[path]
    ]
    if changed:
        # Prioritize XML files if any changed
        xml_paths = [p for p in changed if p.suffix.lower() == ".xml" or "xml" in p.name.lower()]
        if xml_paths:
            newest_xml = sorted(xml_paths, key=lambda path: after[path])[-1]
            text = _read_text(newest_xml, limit=12_000)
            if text.strip():
                return text

        newest = sorted(changed, key=lambda path: after[path])[-1]
        return _read_text(newest, limit=12_000)
    
    # 2. Fallback: On Windows NTFS, mtime updates can be delayed or throttled for identical writes.
    # Retrieve the absolute newest file in the scratch folder regardless of pre-run mtime state.
    if after:
        # Prioritize XML files among all scratch files
        xml_paths = [p for p in after.keys() if p.suffix.lower() == ".xml" or "xml" in p.name.lower()]
        if xml_paths:
            newest_xml = sorted(xml_paths, key=lambda path: after[path])[-1]
            text = _read_text(newest_xml, limit=12_000)
            if text.strip():
                return text

        newest = sorted(after.keys(), key=lambda path: after[path])[-1]
        text = _read_text(newest, limit=12_000)
        if text.strip():
            return text
            
    return ""


def _read_text(path: Path, limit: int) -> str:
    try:
        data = path.read_bytes()
    except Exception:
        return ""
    if len(data) > limit:
        data = data[-limit:]
    return data.decode("utf-8", errors="replace")


def _extract_conversation_id(log_text: str) -> str:
    marker = "Created conversation "
    for line in log_text.splitlines():
        if marker not in line:
            continue
        value = line.split(marker, 1)[1].strip()
        if value:
            return value.split()[0]
    marker = "Print mode: conversation="
    for line in log_text.splitlines():
        if marker not in line:
            continue
        value = line.split(marker, 1)[1].strip()
        if value:
            return value.split(",", 1)[0].strip()
    return ""


def _resolve_session_id(workspace: Path, policy: str, name: str, explicit_session_id: str) -> str:
    if policy == "new":
        return ""
    if policy == "explicit":
        if not explicit_session_id:
            raise ValueError("AGENT_BRIDGE_ANTIGRAVITY_SESSION_ID is required when session policy is explicit")
        return explicit_session_id
    if policy == "continue_named":
        state = _read_session_state(workspace, name)
        return str(state.get("session_id", "")).strip()
    raise ValueError(f"Unsupported session policy: {policy}")


def _session_state_path(workspace: Path, name: str) -> Path:
    safe_name = "".join(c for c in name if c.isalnum() or c in ("_", "-")).strip() or "default"
    return workspace / ".agent" / "sessions" / f"{safe_name}.json"


def _read_session_state(workspace: Path, name: str) -> dict[str, Any]:
    path = _session_state_path(workspace, name)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}


def _write_session_state(workspace: Path, name: str, session_id: str) -> None:
    path = _session_state_path(workspace, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "session_id": session_id,
        "session_name": name,
        "updated_at_unix_ms": int(time.time() * 1000),
    }
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def _emit_event(request_id: str, kind: str, message: str) -> None:
    payload = json.dumps(
        {
            "contract": CONTRACT_VERSION,
            "type": "event",
            "request_id": request_id,
            "event": {"kind": kind, "ts": "adapter", "message": message, "data": {}},
        },
        ensure_ascii=False,
    )
    sys.stdout.buffer.write(payload.encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


def _emit_response(request_id: str, result: dict[str, Any]) -> None:
    payload = json.dumps(
        {
            "contract": CONTRACT_VERSION,
            "type": "response",
            "request_id": request_id,
            "ok": bool(result["ok"]),
            "data": {
                "run_status": result["run_status"],
                "result_summary": result["summary"],
                "artifacts": result.get("artifacts", []),
            },
            "error": result.get("error"),
            "metrics": result.get("metrics", {}),
        },
        ensure_ascii=False,
    )
    sys.stdout.buffer.write(payload.encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    raise SystemExit(main())
