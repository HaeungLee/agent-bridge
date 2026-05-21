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
    try:
        request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        request_id = request["request_id"]
        _emit_event(request_id, "progress", "opencode readonly adapter started")
        result = _run_opencode(request)
        _emit_response(request_id, result)
        return 0
    except Exception as exc:
        request_id = _safe_request_id()
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
    timeout_ms = int(os.environ.get("AGENT_BRIDGE_OPENCODE_TIMEOUT_MS", "120000"))
    task_prompt = str(payload.get("task_prompt") or "")
    message = _readonly_message(task_prompt)

    cmd = [
        "opencode",
        "run",
        "--model",
        model,
        "--format",
        "json",
        "--dir",
        str(workspace),
    ]
    if agent:
        cmd.extend(["--agent", agent])
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
    empty_output = not stdout.strip() and not stderr.strip()
    missing_smoke_token = SMOKE_TOKEN not in text_output
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
        },
        "error": None if ok else {"code": "opencode_failed", "message": opencode_error or stderr[-STDERR_PREVIEW_CHARS:] or summary},
    }


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


def _safe_request_id() -> str:
    try:
        return json.loads(sys.stdin.buffer.read().decode("utf-8")).get("request_id", "")
    except Exception:
        return ""


def _first_filesystem_scope(constraints: dict[str, Any]) -> str:
    scope = constraints.get("filesystem_scope") or []
    if isinstance(scope, list) and scope:
        return str(scope[0])
    return ""


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


if __name__ == "__main__":
    raise SystemExit(main())
