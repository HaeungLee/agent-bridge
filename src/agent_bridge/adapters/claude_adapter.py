import json
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "adapter.v0.1"
STDOUT_PREVIEW_CHARS = 16_000
STDERR_PREVIEW_CHARS = 4_000
FINAL_REPORT_CHARS = 80_000


def main() -> int:
    # Read stdin once and cache
    raw = sys.stdin.buffer.read()
    request_id = ""
    try:
        request = json.loads(raw.decode("utf-8"))
        request_id = request.get("request_id", "")
        _emit_event(request_id, "progress", "claude proxy-redirected adapter started")
        result = _run_claude(request)
        _emit_response(request_id, result)
        return 0
    except Exception as exc:
        _emit_response(
            request_id,
            {
                "ok": False,
                "run_status": "failed",
                "summary": f"Claude proxy adapter failed: {exc}",
                "artifacts": [],
                "metrics": {},
                "error": {"code": "adapter_error", "message": str(exc)},
            },
        )
        return 1


def _is_proxy_running(host: str = "127.0.0.1", port: int = 9001) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except Exception:
        return False


def _load_env_file(workspace_path: Path) -> dict[str, str]:
    env_data = {}
    env_paths = [workspace_path / ".env", Path(os.getcwd()) / ".env"]
    for path in env_paths:
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            env_data[k.strip()] = v.strip()
            except Exception:
                pass
    return env_data


def _run_claude(request: dict[str, Any]) -> dict[str, Any]:
    payload = request.get("payload") or {}
    context = request.get("context") or {}
    constraints = context.get("constraints") or {}
    workspace_path = payload.get("workspace_path") or _first_filesystem_scope(constraints)
    if not workspace_path:
        raise ValueError("workspace_path is required")

    workspace = Path(workspace_path)
    if not workspace.exists() or not workspace.is_dir():
        raise ValueError(f"workspace_path is not a directory: {workspace}")

    request_id = request.get("request_id", "")

    # Load environment variables (command name, paths, etc.)
    cmd_name = os.environ.get("AGENT_BRIDGE_CLAUDE_COMMAND", "claude").strip()
    timeout_ms = int(os.environ.get("AGENT_BRIDGE_CLAUDE_TIMEOUT_MS", "300000"))
    session_policy = os.environ.get("AGENT_BRIDGE_CLAUDE_SESSION_POLICY", "continue_named").strip() or "continue_named"
    session_name = os.environ.get("AGENT_BRIDGE_CLAUDE_SESSION_NAME", "opencode_deepseek_flash").strip() or "default"
    explicit_session_id = os.environ.get("AGENT_BRIDGE_CLAUDE_SESSION_ID", "").strip()
    
    proxy_path = os.environ.get("AGENT_BRIDGE_CLAUDE_PROXY_PATH", "").strip()
    max_budget = os.environ.get("AGENT_BRIDGE_CLAUDE_MAX_BUDGET_USD", "").strip()
    model_name = os.environ.get("AGENT_BRIDGE_CLAUDE_MODEL", "").strip()
    if not model_name:
        model_name = os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL", "").strip()
    
    # 1. Manage proxy daemon lifecycle
    proxy_process = None
    if not _is_proxy_running(port=9001):
        if proxy_path and Path(proxy_path).exists():
            _emit_event(request_id, "progress", f"Spawning local translation proxy: {proxy_path}")
            proxy_process = subprocess.Popen(
                [sys.executable, str(proxy_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Wait for socket bind
            time.sleep(1.0)
        else:
            _emit_event(request_id, "warning", "Local proxy (9001) not running and AGENT_BRIDGE_CLAUDE_PROXY_PATH not found.")

    # 2. Resolve or generate valid UUID session ID (as required by Claude CLI)
    session_id = _resolve_session_id(workspace, session_policy, session_name, explicit_session_id)
    session_reused = bool(_read_session_state(workspace, session_name).get("session_id"))
    
    task_prompt = str(payload.get("task_prompt") or "")
    message = _build_message(task_prompt)

    # 3. Assemble command parameters (bypass permissions completely for automation)
    cmd = [
        cmd_name,
        "-p",
        message,
        "--output-format",
        "stream-json",
        "--verbose",
        "--dangerously-skip-permissions",
        "--permission-mode",
        "bypassPermissions",
    ]
    if model_name:
        cmd.extend(["--model", model_name])
    if session_id:
        cmd.extend(["--session-id", session_id])
    if max_budget:
        cmd.extend(["--max-budget-usd", max_budget])

    # 4. Prepare bypass environment variables
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    env["ANTHROPIC_BASE_URL"] = "http://localhost:9001/v1"
    
    # Load keys from .env if needed
    dotenv = _load_env_file(workspace)
    nano_key = dotenv.get("NANOGPT_API_KEY", "").strip()
    if nano_key:
        env["ANTHROPIC_API_KEY"] = nano_key
    elif "ANTHROPIC_API_KEY" not in env:
        # Fallback to local process env
        env["ANTHROPIC_API_KEY"] = os.environ.get("NANOGPT_API_KEY", "").strip()

    env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = "deepseek/deepseek-v4-flash"

    started = time.time()
    
    text_accumulator = []
    plain_text_lines = []  # fallback for non-JSON output
    tool_uses = []
    session_info = {"session_id": session_id, "cost": 0.0}
    
    try:
        # 5. Start Claude Code process with streaming pipes (binary mode to avoid cp949 on Windows)
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            shell=True,
            bufsize=0,  # unbuffered binary
        )
        
        # Read stdout line-by-line in binary mode, decode as utf-8
        stdout_lines = []
        for raw_line in iter(process.stdout.readline, b""):
            line_str = raw_line.decode("utf-8", errors="replace")
            stdout_lines.append(line_str)
            parsed = _parse_stream_line(line_str, request_id, text_accumulator, tool_uses, session_info)
            if not parsed and line_str.strip():
                plain_text_lines.append(line_str)
            
        # Capture remaining stderr (binary decode)
        stderr_bytes = process.stderr.read()
        stderr_str = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
        
        exit_code = process.wait(timeout=10.0)
        
    except Exception as exc:
        raise exc
        
    finally:
        # 6. Terminate proxy if auto-spawned in this turn
        if proxy_process is not None:
            try:
                _emit_event(request_id, "progress", "Terminating local proxy daemon")
                proxy_process.terminate()
                proxy_process.wait(timeout=5.0)
            except Exception:
                pass

    elapsed_ms = int((time.time() - started) * 1000)
    stdout_full = "".join(stdout_lines)
    
    # Write session state on successful continuation
    observed_session_id = session_info.get("session_id") or session_id
    if observed_session_id and session_policy == "continue_named":
        _write_session_state(workspace, session_name, observed_session_id)

    text_output = "".join(text_accumulator).strip()
    # Fallback: use plain text output when stream-json parsing yields nothing
    if not text_output and plain_text_lines:
        text_output = "".join(plain_text_lines).strip()
    final_report = text_output[:FINAL_REPORT_CHARS]
    
    # Evaluate run status: exit 0 is success even if text is empty
    ok = exit_code == 0
    summary = f"Claude proxy adapter exited {exit_code}. Response: {text_output.replace(chr(10), ' ')[:240]}"
    if not text_output and exit_code == 0:
        summary = "Claude proxy adapter exited 0 but produced no text output."
        
    return {
        "ok": ok,
        "run_status": "completed" if ok else "failed",
        "summary": summary,
        "artifacts": [
            {
                "kind": "final_report",
                "text": final_report,
            },
            {
                "kind": "tool_use_summary",
                "items": tool_uses,
            },
            {
                "kind": "stdout_preview",
                "text": stdout_full[:STDOUT_PREVIEW_CHARS],
            },
            {
                "kind": "stderr_preview",
                "text": stderr_str[:STDERR_PREVIEW_CHARS],
            },
        ],
        "metrics": {
            "elapsed_ms": elapsed_ms,
            "cost_usd": session_info.get("cost") or 0.0,
            "tokens_in": None,
            "tokens_out": None,
            "session_id": observed_session_id,
            "session_reused": session_reused,
            "session_policy": session_policy,
            "session_name": session_name,
        },
        "error": None if ok else {"code": "claude_failed", "message": stderr_str or summary},
    }


def _build_message(task_prompt: str) -> str:
    # Prepare message body mimicking implementation instructions
    task_text = task_prompt.strip().replace("\r\n", "\n")
    if os.environ.get("AGENT_BRIDGE_CLAUDE_IMPLEMENTATION", "").strip().lower() in {"1", "true", "yes"}:
        return "\n".join(
            [
                "You are running under agent-bridge implementation mode.",
                "Follow the rendered task prompt exactly.",
                "Modify only files listed in Allowed Files.",
                "Do not modify Forbidden Files.",
                "Do not commit.",
                "If the task cannot be completed within scope, stop and report the blocker.",
                "",
                task_text,
            ]
        )
    return task_text


def _parse_stream_line(line_str: str, request_id: str, text_accumulator: list[str], tool_uses: list[dict], session_info: dict) -> bool:
    """Parse a single stream line. Returns True if it was valid JSON (parsed), False otherwise."""
    line_str = line_str.strip()
    if not line_str:
        return False
    try:
        frame = json.loads(line_str)
    except json.JSONDecodeError:
        return False

    frame_type = frame.get("type")
    
    if frame_type == "system":
        session_id = frame.get("session_id")
        if session_id:
            session_info["session_id"] = session_id
            _emit_event(request_id, "progress", f"Claude session initialized: {session_id}")
            
    elif frame_type == "assistant":
        msg = frame.get("message") or {}
        content = msg.get("content") or []
        for block in content:
            block_type = block.get("type")
            if block_type == "text":
                txt = block.get("text", "")
                if txt:
                    text_accumulator.append(txt)
            elif block_type == "tool_use":
                tool_name = block.get("name")
                tool_input = block.get("input") or {}
                paths = []
                for key in ("filePath", "filepath", "path", "target_file", "targetPath", "file_path"):
                    val = tool_input.get(key)
                    if isinstance(val, str) and val.strip():
                        paths.append(val.strip())
                tool_uses.append({
                    "tool": tool_name,
                    "status": "call",
                    "paths": paths
                })
                _emit_event(request_id, "progress", f"Claude using tool: {tool_name} {paths}")
                
    elif frame_type == "result":
        res = frame.get("result")
        if res:
            text_accumulator.append(res)
        cost = frame.get("total_cost_usd")
        if cost is not None:
            session_info["cost"] = cost

    return True


def _first_filesystem_scope(constraints: dict[str, Any]) -> str:
    scope = constraints.get("filesystem_scope") or []
    if isinstance(scope, list) and scope:
        return str(scope[0])
    return ""


def _resolve_session_id(workspace: Path, policy: str, name: str, explicit_session_id: str) -> str:
    if policy == "new":
        return str(uuid.uuid4())
    if policy == "explicit":
        if not explicit_session_id:
            raise ValueError("AGENT_BRIDGE_CLAUDE_SESSION_ID is required when session policy is explicit")
        try:
            uuid.UUID(explicit_session_id)
            return explicit_session_id
        except ValueError:
            raise ValueError(f"explicit session ID must be a valid UUID: {explicit_session_id}")
    if policy == "continue_named":
        state = _read_session_state(workspace, name)
        saved_id = str(state.get("session_id", "")).strip()
        if saved_id:
            try:
                uuid.UUID(saved_id)
                return saved_id
            except ValueError:
                pass
        # Generate new valid UUIDv4 if missing/invalid
        new_id = str(uuid.uuid4())
        _write_session_state(workspace, name, new_id)
        return new_id
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
