import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "adapter.v0.1"
STDOUT_PREVIEW_CHARS = 12_000
STDERR_PREVIEW_CHARS = 4_000
SMOKE_TOKEN = "AGENT_BRIDGE_OPENCODE_SMOKE_OK"


def main() -> int:
    # Read stdin once and cache; _safe_request_id() must not re-read stdin.
    raw = sys.stdin.buffer.read()
    request_id = ""
    try:
        request = json.loads(raw.decode("utf-8"))
        request_id = request.get("request_id", "")
        _emit_event(request_id, "progress", "opencode readonly adapter started")
        result = _run_opencode(request)
        _emit_response(request_id, result)
        return 0
    except Exception as exc:
        _emit_response(
            request_id,
            {
                "ok": False,
                "run_status": "failed",
                "summary": f"OpenCode readonly adapter failed: {exc}",
                "artifacts": [],
                "metrics": {},
                "error": {"code": "adapter_error", "message": str(exc)},
            },
        )
        return 1


def _run_opencode(request: dict[str, Any]) -> dict[str, Any]:
    payload = request.get("payload") or {}
    context = request.get("context") or {}
    constraints = context.get("constraints") or {}
    workspace_path = payload.get("workspace_path") or _first_filesystem_scope(constraints)
    if not workspace_path:
        raise ValueError("workspace_path is required")

    workspace = Path(workspace_path)
    if not workspace.exists() or not workspace.is_dir():
        raise ValueError(f"workspace_path is not a directory: {workspace}")

    model = os.environ.get("AGENT_BRIDGE_OPENCODE_MODEL", "").strip()
    if not model:
        raise ValueError("AGENT_BRIDGE_OPENCODE_MODEL is required")

    agent = os.environ.get("AGENT_BRIDGE_OPENCODE_AGENT", "").strip()
    pure = os.environ.get("AGENT_BRIDGE_OPENCODE_PURE", "").strip().lower() in {"1", "true", "yes"}
    timeout_ms = int(os.environ.get("AGENT_BRIDGE_OPENCODE_TIMEOUT_MS", "120000"))
    session_policy = os.environ.get("AGENT_BRIDGE_OPENCODE_SESSION_POLICY", "new").strip() or "new"
    session_name = os.environ.get("AGENT_BRIDGE_OPENCODE_SESSION_NAME", "").strip() or "default"
    explicit_session_id = os.environ.get("AGENT_BRIDGE_OPENCODE_SESSION_ID", "").strip()
    session_id = _resolve_session_id(workspace, session_policy, session_name, explicit_session_id)
    task_prompt = str(payload.get("task_prompt") or "")
    message = _build_message(task_prompt, bool(session_id))

    cmd = [
        "opencode",
    ]
    if pure:
        cmd.append("--pure")
    cmd.extend([
        "run",
        "--model",
        model,
        "--format",
        "json",
        "--dir",
        str(workspace),
    ])
    if agent:
        cmd.extend(["--agent", agent])
    if session_id:
        cmd.extend(["--session", session_id])
    cmd.append(message)

    started = time.time()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_ms / 1000.0,
        shell=False,
    )
    elapsed_ms = int((time.time() - started) * 1000)
    stdout = result.stdout or ""
    stderr = result.stderr or ""

    opencode_error = _extract_opencode_error(stdout)
    text_output = _extract_opencode_text(stdout)
    observed_session_id = _extract_session_id(stdout) or session_id
    session_reused = bool(session_id)
    if observed_session_id and session_policy == "continue_named":
        _write_session_state(workspace, session_name, observed_session_id)
    direct_smoke = os.environ.get("AGENT_BRIDGE_OPENCODE_DIRECT_SMOKE", "").strip().lower() in {"1", "true", "yes"}
    empty_output = not stdout.strip() and not stderr.strip()
    # Smoke token check is only required in direct-smoke mode.
    # In report/task mode, absence of the token is not an error.
    missing_smoke_token = direct_smoke and (SMOKE_TOKEN not in text_output)
    ok = result.returncode == 0 and opencode_error == "" and not empty_output and not missing_smoke_token
    summary = _summarize_opencode_output(stdout, stderr, result.returncode, text_output)
    if opencode_error:
        summary = f"OpenCode reported an error: {opencode_error}"
    elif empty_output:
        summary = "OpenCode exited 0 but produced no stdout or stderr."
    elif missing_smoke_token:
        summary = f"OpenCode output did not include required smoke token {SMOKE_TOKEN}."
    return {
        "ok": ok,
        "run_status": "completed" if ok else "failed",
        "summary": summary,
        "artifacts": [
            {
                "kind": "tool_use_summary",
                "items": _extract_tool_use_summary(stdout),
            },
            {
                "kind": "stdout_preview",
                "text": stdout[:STDOUT_PREVIEW_CHARS],
            },
            {
                "kind": "stderr_preview",
                "text": stderr[:STDERR_PREVIEW_CHARS],
            },
        ],
        "metrics": {
            "elapsed_ms": elapsed_ms,
            "cost_usd": 0.0,
            "tokens_in": None,
            "tokens_out": None,
            "session_id": observed_session_id,
            "session_reused": session_reused,
            "session_policy": session_policy,
            "session_name": session_name,
        },
        "error": None if ok else {"code": "opencode_failed", "message": opencode_error or stderr[-STDERR_PREVIEW_CHARS:] or summary},
    }


def _build_message(task_prompt: str, has_session: bool) -> str:
    if _truthy_env("AGENT_BRIDGE_OPENCODE_DIRECT_SMOKE"):
        if has_session:
            return "What exact smoke token were you asked to remember in the previous turn? Reply with only that token."
        return f"Remember this smoke token for the next turn: {SMOKE_TOKEN}. Reply with exactly: {SMOKE_TOKEN}."
    if _truthy_env("AGENT_BRIDGE_OPENCODE_COMPACT_REPORT"):
        return _compact_report_message(task_prompt)
    return _readonly_message(task_prompt)


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def _compact_report_message(task_prompt: str) -> str:
    files = _extract_rendered_list(task_prompt, "Allowed Files")
    inspect_files = _benchmark_target_files(files)
    inspect_text = ", ".join(inspect_files) if inspect_files else "the rendered task's explicit allowed files"
    objective = _extract_rendered_section(task_prompt, "Objective")[:600]
    focus_line = objective if objective else "Return a compact factual report about the requested repository slice."
    return "\n".join(
        [
            "Read-only repository report.",
            "Do not modify files or create files.",
            "Use only read/grep/glob style inspection if tool use is needed.",
            f"Inspect only: {inspect_text}.",
            "Report factual findings in 6 bullets.",
            f"Focus: {focus_line}",
        ]
    )


def _benchmark_target_files(files: list[str]) -> list[str]:
    ignored_prefixes = (
        ".agent/tasks/",
        "docs/process/",
        "roadmap.md",
    )
    targets = [
        path for path in files
        if not any(path.startswith(prefix) for prefix in ignored_prefixes)
    ]
    return targets[:4] or files[:3]


def _extract_rendered_list(task_prompt: str, heading: str) -> list[str]:
    lines = task_prompt.replace("\r\n", "\n").splitlines()
    marker = f"## {heading}"
    items: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped == marker:
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if not in_section or not stripped.startswith("- "):
            continue
        value = stripped[2:].strip()
        if value.startswith("`") and value.endswith("`") and len(value) >= 2:
            value = value[1:-1]
        if value:
            items.append(value)
    return items


def _extract_rendered_section(task_prompt: str, heading: str) -> str:
    lines = task_prompt.replace("\r\n", "\n").splitlines()
    marker = f"## {heading}"
    collected: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped == marker:
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if in_section:
            collected.append(line)
    return "\n".join(collected).strip()


def _readonly_message(task_prompt: str) -> str:
    task_preview = task_prompt.strip().replace("\r\n", "\n")[:1200]
    return "\n".join(
        [
            "You are running under agent-bridge Phase 5-B read-only smoke.",
            "Do not modify files.",
            "Do not create files.",
            "Do not run write commands.",
            "Do not use tools.",
            "The adapter received a rendered task prompt and is passing a compact preview to you.",
            f"Rendered task prompt length: {len(task_prompt)} characters.",
            f"Your final response must include this exact token: {SMOKE_TOKEN}.",
            "Return only a compact smoke report with Changed files, Commands run, Result, Risks, Open questions, Next recommended step.",
            "",
            "Task prompt preview:",
            task_preview,
        ]
    )


def _emit_event(request_id: str, kind: str, message: str) -> None:
    print(
        json.dumps(
            {
                "contract": CONTRACT_VERSION,
                "type": "event",
                "request_id": request_id,
                "event": {"kind": kind, "ts": "adapter", "message": message, "data": {}},
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


def _emit_response(request_id: str, result: dict[str, Any]) -> None:
    print(
        json.dumps(
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
        ),
        flush=True,
    )


# Removed: _safe_request_id() was re-reading stdin which is always empty after main() reads it.
# request_id is now captured in main() before the try block.


def _first_filesystem_scope(constraints: dict[str, Any]) -> str:
    scope = constraints.get("filesystem_scope") or []
    if isinstance(scope, list) and scope:
        return str(scope[0])
    return ""


def _resolve_session_id(workspace: Path, policy: str, name: str, explicit_session_id: str) -> str:
    if policy == "new":
        return ""
    if policy == "explicit":
        if not explicit_session_id:
            raise ValueError("AGENT_BRIDGE_OPENCODE_SESSION_ID is required when session policy is explicit")
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
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}
    return data


def _write_session_state(workspace: Path, name: str, session_id: str) -> None:
    path = _session_state_path(workspace, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "session_id": session_id,
        "session_name": name,
        "updated_at_unix_ms": int(time.time() * 1000),
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _summarize_opencode_output(stdout: str, stderr: str, exit_code: int, text_output: str) -> str:
    if text_output:
        preview = text_output.replace("\n", " ")[:240]
        return f"OpenCode readonly smoke exited {exit_code}. Text output: {preview}"
    if stdout.strip():
        return f"OpenCode readonly smoke exited {exit_code}. Captured {len(stdout)} stdout chars and {len(stderr)} stderr chars."
    return f"OpenCode readonly smoke exited {exit_code}. No stdout captured. Stderr chars: {len(stderr)}."


def _extract_opencode_error(stdout: str) -> str:
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            frame = json.loads(line)
        except json.JSONDecodeError:
            continue
        if frame.get("type") != "error":
            continue
        error = frame.get("error")
        if isinstance(error, dict):
            data = error.get("data")
            if isinstance(data, dict) and isinstance(data.get("message"), str):
                return data["message"]
            if isinstance(error.get("message"), str):
                return error["message"]
        return "unknown opencode error"
    return ""


def _extract_session_id(stdout: str) -> str:
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            frame = json.loads(line)
        except json.JSONDecodeError:
            continue
        session_id = frame.get("sessionID")
        if isinstance(session_id, str) and session_id:
            return session_id
        part = frame.get("part")
        if isinstance(part, dict):
            session_id = part.get("sessionID")
            if isinstance(session_id, str) and session_id:
                return session_id
    return ""


def _extract_opencode_text(stdout: str) -> str:
    texts: list[str] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            frame = json.loads(line)
        except json.JSONDecodeError:
            continue
        if frame.get("type") != "text":
            continue
        part = frame.get("part")
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            texts.append(part["text"])
    return "\n".join(texts).strip()


def _extract_tool_use_summary(stdout: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            frame = json.loads(line)
        except json.JSONDecodeError:
            continue
        if frame.get("type") != "tool_use":
            continue
        part = frame.get("part")
        if not isinstance(part, dict):
            continue
        state = part.get("state")
        if not isinstance(state, dict):
            state = {}
        input_data = state.get("input")
        if not isinstance(input_data, dict):
            input_data = {}
        paths: list[str] = []
        for key in ("filePath", "filepath", "path", "target_file", "targetPath"):
            value = input_data.get(key)
            if isinstance(value, str) and value.strip():
                paths.append(value.strip())
        items.append(
            {
                "tool": part.get("tool") or "",
                "status": state.get("status") or "",
                "paths": paths,
            }
        )
    return items


if __name__ == "__main__":
    raise SystemExit(main())
