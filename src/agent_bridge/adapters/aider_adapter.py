import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "adapter.v0.1"
STDOUT_PREVIEW_CHARS = 16_000
STDERR_PREVIEW_CHARS = 4_000
FINAL_REPORT_CHARS = 80_000


def main() -> int:
    raw = sys.stdin.buffer.read()
    request_id = ""
    try:
        request = json.loads(raw.decode("utf-8"))
        request_id = request.get("request_id", "")
        _emit_event(request_id, "progress", "Aider direct nanoGPT adapter started")
        result = _run_aider(request)
        _emit_response(request_id, result)
        return 0
    except Exception as exc:
        _emit_response(
            request_id,
            {
                "ok": False,
                "run_status": "failed",
                "summary": f"Aider adapter failed: {exc}",
                "artifacts": [],
                "metrics": {},
                "error": {"code": "adapter_error", "message": str(exc)},
            },
        )
        return 1


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


def _run_aider(request: dict[str, Any]) -> dict[str, Any]:
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

    # Load parameters from environment or config override
    cmd_name = os.environ.get("AGENT_BRIDGE_AIDER_COMMAND", "aider").strip()
    timeout_ms = int(os.environ.get("AGENT_BRIDGE_AIDER_TIMEOUT_MS", "300000"))
    model_name = os.environ.get("AGENT_BRIDGE_AIDER_MODEL", "openai/deepseek/deepseek-v4-pro").strip()
    session_name = os.environ.get("AGENT_BRIDGE_AIDER_SESSION_NAME", "").strip()
    restore_chat_history = os.environ.get("AGENT_BRIDGE_AIDER_RESTORE_CHAT_HISTORY", "").strip().lower() in {"1", "true", "yes"}

    task_prompt = str(payload.get("task_prompt") or "")
    history_root = Path(tempfile.gettempdir()) / "agent-bridge-aider"
    history_root.mkdir(parents=True, exist_ok=True)
    history_seed = session_name or request_id
    history_suffix = "".join(c for c in history_seed if c.isalnum() or c in ("-", "_")) or "session"

    # 1. Assemble Aider commands for batch mode Execution
    cmd = [
        _resolve_command(cmd_name),
        "--model", model_name,
        "--no-auto-commits",
        "--yes-always",
        "--no-pretty",
        "--no-fancy-input",
        "--no-show-model-warnings",
        "--encoding", "utf-8",
        "--map-tokens", "0",
        "--no-gitignore",
        "--no-analytics",
        "--input-history-file", str(history_root / f"{history_suffix}.input.history"),
        "--chat-history-file", str(history_root / f"{history_suffix}.chat.history.md"),
        "--llm-history-file", str(history_root / f"{history_suffix}.llm.history.md"),
        "--restore-chat-history" if restore_chat_history else "--no-restore-chat-history",
        "--message", task_prompt,
    ]

    # 2. Build direct nanoGPT E2E execution environment
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["AIDER_PRETTY"] = "false"
    env["AIDER_FANCY_INPUT"] = "false"
    env["AIDER_SHOW_MODEL_WARNINGS"] = "false"
    env["AIDER_ENCODING"] = "utf-8"
    env["AIDER_MAP_TOKENS"] = "0"
    env["AIDER_GITIGNORE"] = "false"
    env["AIDER_ANALYTICS"] = "false"
    
    # Load keys from .env if needed
    dotenv = _load_env_file(workspace)
    nano_key = dotenv.get("NANOGPT_API_KEY", "").strip()
    if not nano_key:
        # Fallback to local process env
        nano_key = os.environ.get("NANOGPT_API_KEY", "").strip()

    if not nano_key:
        raise ValueError("NANOGPT_API_KEY must be specified in .env or environment")

    # Aider internally uses litellm which resolves OpenAI variables
    env["OPENAI_API_KEY"] = nano_key
    env["OPENAI_API_BASE"] = "https://nano-gpt.com/api/v1"

    started = time.time()
    
    stdout_lines = []
    stderr_lines = []
    
    try:
        # 3. Start Aider subprocess with streaming pipes
        process = subprocess.Popen(
            _prepare_subprocess_command(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(workspace.resolve()),
            env=env,
            shell=False,
            bufsize=0,
        )
        
        # Real-time stdout capture (decode as replace to avoid crash on complex characters)
        for raw_line in iter(process.stdout.readline, b""):
            line_str = raw_line.decode("utf-8", errors="replace")
            stdout_lines.append(line_str)
            # Emit simple progress so CLI stays alive and visually reactive
            _emit_event(request_id, "progress", line_str.strip())
            
        # Capture stderr
        stderr_bytes = process.stderr.read()
        stderr_str = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
        
        exit_code = process.wait(timeout=10.0)
        
    except Exception as exc:
        raise exc

    elapsed_ms = int((time.time() - started) * 1000)
    stdout_full = "".join(stdout_lines)
    
    # Build complete final report
    final_report = stdout_full[:FINAL_REPORT_CHARS]
    
    ok = exit_code == 0
    summary = f"Aider adapter exited {exit_code}. Output preview: {stdout_full.replace(chr(10), ' ')[:240]}"
    if not stdout_full.strip() and exit_code == 0:
        summary = "Aider adapter completed successfully but returned no stdout."
        
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
            "cost_usd": 0.0,  # Litellm doesn't output exact billing directly in pure subprocess
            "tokens_in": None,
            "tokens_out": None,
            "model": model_name,
            "openai_api_base": env["OPENAI_API_BASE"],
            "session_name": session_name or None,
            "restore_chat_history": restore_chat_history,
        },
        "error": None if ok else {"code": "aider_failed", "message": stderr_str or summary},
    }


def _first_filesystem_scope(constraints: dict[str, Any]) -> str:
    scope = constraints.get("filesystem_scope") or []
    if isinstance(scope, list) and scope:
        return str(scope[0])
    return ""


def _resolve_command(command: str) -> str:
    # 1. Try default system PATH resolution
    resolved = shutil.which(command)
    if resolved:
        return resolved

    # 2. If it is Windows and we are looking for 'aider', scan typical local installation paths
    if command == "aider" and os.name == "nt":
        home = Path.home()
        fallback_paths = [
            home / ".local" / "bin" / "aider.exe",
            home / ".local" / "bin" / "aider",
            home / "AppData" / "Roaming" / "uv" / "tools" / "aider-chat" / "Scripts" / "aider.exe",
            home / "AppData" / "Roaming" / "uv" / "tools" / "aider-chat" / "Scripts" / "aider",
        ]
        for path in fallback_paths:
            if path.exists():
                return str(path.resolve())

    return command


def _prepare_subprocess_command(cmd: list[str]) -> list[str]:
    if os.name != "nt":
        return cmd
    suffix = Path(cmd[0]).suffix.lower()
    if suffix in {".cmd", ".bat"}:
        comspec = os.environ.get("ComSpec", "cmd.exe")
        return [comspec, "/d", "/s", "/c", *cmd]
    if suffix == ".ps1":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", *cmd]
    return cmd


def _emit_event(request_id: str, kind: str, message: str) -> None:
    if not message.strip():
        return
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
