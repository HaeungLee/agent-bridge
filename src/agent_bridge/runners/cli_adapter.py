import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_bridge.runners.base import Runner, RunnerResult

ADAPTER_CONTRACT_VERSION = "adapter.v0.1"
MAX_REQUEST_BYTES = 64 * 1024
MAX_EVENT_LINE_BYTES = 64 * 1024
MAX_RESPONSE_LINE_BYTES = 512 * 1024
STDERR_PREVIEW_CHARS = 1024

ALLOWED_METHODS = {"health", "capabilities", "plan", "execute", "review", "test"}
ALLOWED_EVENT_KINDS = {"progress", "log", "artifact", "warning", "metric"}
ALLOWED_RUN_STATUS = {"completed", "partial", "failed", "needs_approval", "blocked"}


@dataclass
class CliAdapterConfig:
    command: str
    args: list[str] = field(default_factory=list)
    allowlist: list[str] = field(default_factory=list)
    timeout_ms: int = 30_000
    env: dict[str, str] = field(default_factory=dict)


def load_cli_adapter_config(runners_config: dict[str, Any], adapter_id: str) -> CliAdapterConfig:
    runner_config = runners_config.get("runners", {}).get("cli_adapter", {})
    adapters = runner_config.get("adapters", {})
    adapter_config = adapters.get(adapter_id)
    if not isinstance(adapter_config, dict):
        raise ValueError(f"Missing config for cli_adapter adapter_id '{adapter_id}'")

    command = adapter_config.get("command")
    if not isinstance(command, str) or not command.strip():
        raise ValueError(f"cli_adapter '{adapter_id}' must define a non-empty command")

    return CliAdapterConfig(
        command=command,
        args=_string_list(adapter_config.get("args", []), f"{adapter_id}.args"),
        allowlist=_string_list(adapter_config.get("allowlist", []), f"{adapter_id}.allowlist"),
        timeout_ms=int(adapter_config.get("timeout_ms", 30_000)),
        env=_string_dict(adapter_config.get("env", {}), f"{adapter_id}.env"),
    )


class CliAdapterRunner(Runner):
    def __init__(self, adapter_id: str, config: CliAdapterConfig):
        self.adapter_id = adapter_id
        self.command = config.command.strip()
        self.args = list(config.args)
        self.allowlist = {
            entry.strip() for entry in (config.allowlist or [self.command]) if entry.strip()
        }
        self.timeout_ms = max(int(config.timeout_ms), 1)
        self.env = dict(config.env)

    def run(self, task_path: Path, workspace_path: Path, timeout_seconds: int) -> RunnerResult:
        # timeout_seconds is already in seconds (converted by caller).
        # Use the larger of the caller-supplied value and the adapter's own config.
        timeout_ms = max(int(timeout_seconds * 1000), self.timeout_ms)
        task_prompt = task_path.read_text(encoding="utf-8")
        run_id = f"cli-{uuid.uuid4().hex[:8]}"
        request = build_request_envelope(
            method="execute",
            payload={
                "plan_id": f"plan-{run_id}",
                "task_prompt": task_prompt,
                "workspace_path": str(workspace_path.resolve()),
                "execution": {
                    "dry_run": False,
                    "require_approval": False,
                },
                "inputs": {
                    "artifact_refs": [],
                },
            },
            run_id=run_id,
            workspace_path=str(workspace_path.resolve()),
            deadline_ms=timeout_ms,
        )

        started = time.time()
        command_display = self._command_display()
        try:
            _events, response, stdout, stderr, exit_code = self.invoke(request, timeout_ms)
            elapsed = time.time() - started
            data = response.get("data") or {}
            response_metrics = response.get("metrics") or {}
            run_status = data.get("run_status", "completed" if response.get("ok") else "failed")
            if run_status not in ALLOWED_RUN_STATUS:
                run_status = "failed"
            summary = data.get("result_summary") or "CLI adapter completed."
            if not response.get("ok"):
                run_status = "failed"
                error = response.get("error") or {}
                summary = error.get("message") or summary
            return RunnerResult(
                status="completed" if run_status == "completed" else run_status,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                summary=summary,
                commands_run=[command_display],
                runtime_seconds=round(elapsed, 4),
                metadata={
                    "adapter_response_metrics": response_metrics,
                    "adapter_artifacts": data.get("artifacts", []),
                    "session_id": response_metrics.get("session_id"),
                    "session_reused": response_metrics.get("session_reused"),
                    "session_policy": response_metrics.get("session_policy"),
                    "session_name": response_metrics.get("session_name"),
                },
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = time.time() - started
            stderr = _decode_bytes(exc.stderr)
            message = f"CLI adapter timed out after {timeout_ms}ms."
            return RunnerResult(
                status="timeout",
                exit_code=None,
                stdout=_decode_bytes(exc.stdout),
                stderr=f"{stderr}\n{message}".strip(),
                summary=message,
                commands_run=[command_display],
                runtime_seconds=round(elapsed, 4),
                metadata={"session_id": None},
            )
        except Exception as exc:
            elapsed = time.time() - started
            return RunnerResult(
                status="failed",
                exit_code=-1,
                stdout="",
                stderr=str(exc),
                summary=f"CLI adapter failed: {exc}",
                commands_run=[command_display],
                runtime_seconds=round(elapsed, 4),
                metadata={"session_id": None},
            )

    def invoke(self, request_envelope: dict[str, Any], timeout_ms: int) -> tuple[list[dict], dict, str, str, int]:
        if not self._is_command_allowlisted():
            raise RuntimeError(f"command_not_allowlisted: {self.command!r}")

        request_line = json.dumps(request_envelope, ensure_ascii=False)
        request_bytes = request_line.encode("utf-8")
        if len(request_bytes) > MAX_REQUEST_BYTES:
            raise RuntimeError(
                f"request_too_large: {len(request_bytes)} bytes > {MAX_REQUEST_BYTES}"
            )

        env = {**os.environ, **self.env}
        cmd = [self.command] + self.args
        result = subprocess.run(
            cmd,
            input=request_bytes,
            capture_output=True,
            timeout=timeout_ms / 1000.0,
            env=env,
            shell=False,
        )

        stdout = result.stdout.decode("utf-8", errors="strict")
        stderr = result.stderr.decode("utf-8", errors="replace")
        events, response = parse_stdout_lines(
            request_id=request_envelope["request_id"],
            adapter_id=self.adapter_id,
            stdout=stdout,
            stderr=stderr,
            exit_code=result.returncode,
        )
        return events, response, stdout, stderr, result.returncode

    def _is_command_allowlisted(self) -> bool:
        if not self.command:
            return False
        return self.command in self.allowlist or Path(self.command).name in self.allowlist

    def _command_display(self) -> str:
        parts = [Path(self.command).name]
        for arg in self.args:
            if len(arg) > 120:
                parts.append("<inline-or-long-arg>")
            else:
                parts.append(arg)
        return " ".join(parts)


def build_request_envelope(
    method: str,
    payload: dict[str, Any],
    run_id: str,
    workspace_path: str,
    deadline_ms: int,
) -> dict[str, Any]:
    if method not in ALLOWED_METHODS:
        raise ValueError(f"unsupported adapter method: {method}")
    return {
        "contract": ADAPTER_CONTRACT_VERSION,
        "type": "request",
        "request_id": str(uuid.uuid4()),
        "method": method,
        "payload": payload,
        "context": {
            "run_id": run_id,
            "session_id": "",
            "user_id": "commander",
            "policy_mode": "default",
            "deadline_ms": deadline_ms,
            "budget": {"max_cost_usd": 0.0, "max_tokens": 0},
            "constraints": {
                "allow_network": False,
                "filesystem_scope": [workspace_path] if workspace_path else [],
                "risk_level": "low",
            },
            "trace": {
                "request_ts": datetime.now(timezone.utc).isoformat(),
                "route_reason": "agent-bridge-commander",
            },
        },
    }


def parse_stdout_lines(
    request_id: str,
    adapter_id: str,
    stdout: str,
    stderr: str,
    exit_code: int,
) -> tuple[list[dict], dict]:
    events: list[dict] = []
    final_response = None
    lines = [line.rstrip("\r") for line in stdout.splitlines() if line.strip()]

    for index, line in enumerate(lines):
        line_bytes = len(line.encode("utf-8"))
        try:
            frame = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"adapter_failure: invalid JSON at line {index}: {exc}") from exc

        frame_type = frame.get("type")
        if frame_type == "event":
            if line_bytes > MAX_EVENT_LINE_BYTES:
                raise RuntimeError(
                    f"adapter_failure: event line {index} exceeds {MAX_EVENT_LINE_BYTES} bytes"
                )
            validate_event(frame, request_id, adapter_id, index)
            events.append(frame)
        elif frame_type == "response":
            if final_response is not None:
                raise RuntimeError(f"adapter_failure: multiple response frames at line {index}")
            if line_bytes > MAX_RESPONSE_LINE_BYTES:
                raise RuntimeError(
                    f"adapter_failure: response line {index} exceeds {MAX_RESPONSE_LINE_BYTES} bytes"
                )
            validate_response(frame, request_id, index)
            final_response = frame
        else:
            raise RuntimeError(
                f"adapter_failure: unsupported frame type {frame_type!r} at line {index}"
            )

    if final_response is None:
        raise RuntimeError(
            "adapter_failure: no final response frame emitted. "
            f"exit_code={exit_code}, stderr={stderr_preview(stderr)}"
        )

    if final_response.get("ok") and exit_code != 0:
        raise RuntimeError(f"adapter_failure: ok=true but non-zero exit code {exit_code}")

    return events, final_response


def validate_event(frame: dict[str, Any], request_id: str, adapter_id: str, index: int) -> None:
    _validate_common_frame(frame, request_id, "event", index)
    event = frame.get("event")
    if not isinstance(event, dict):
        raise RuntimeError(f"adapter_failure: event frame at line {index} missing event object")
    kind = event.get("kind", "")
    if kind in ALLOWED_EVENT_KINDS:
        return
    prefix = f"x.{adapter_id}."
    if not (isinstance(kind, str) and kind.startswith(prefix) and len(kind) > len(prefix)):
        raise RuntimeError(f"adapter_failure: event kind {kind!r} not allowed at line {index}")


def validate_response(frame: dict[str, Any], request_id: str, index: int) -> None:
    _validate_common_frame(frame, request_id, "response", index)
    if "ok" not in frame or not isinstance(frame.get("ok"), bool):
        raise RuntimeError(f"adapter_failure: response at line {index} missing boolean ok")


def _validate_common_frame(frame: dict[str, Any], request_id: str, frame_type: str, index: int) -> None:
    if frame.get("contract") != ADAPTER_CONTRACT_VERSION:
        raise RuntimeError(f"adapter_failure: {frame_type} contract mismatch at line {index}")
    if frame.get("type") != frame_type:
        raise RuntimeError(f"adapter_failure: expected {frame_type} frame at line {index}")
    if frame.get("request_id") != request_id:
        raise RuntimeError(f"adapter_failure: {frame_type} request_id mismatch at line {index}")


def stderr_preview(stderr: str) -> str:
    text = stderr.strip()
    if len(text) > STDERR_PREVIEW_CHARS:
        return text[:STDERR_PREVIEW_CHARS] + "..."
    return text


def _decode_bytes(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.decode("utf-8", errors="replace")


def make_local_smoke_config() -> CliAdapterConfig:
    script = (
        "import json,sys,time;"
        "req=json.loads(sys.stdin.buffer.read().decode('utf-8'));"
        "rid=req['request_id'];"
        "print(json.dumps({'contract':'adapter.v0.1','type':'event','request_id':rid,"
        "'event':{'kind':'progress','ts':'smoke','message':'local smoke adapter started','data':{}}}));"
        "print(json.dumps({'contract':'adapter.v0.1','type':'response','request_id':rid,"
        "'ok':True,'data':{'run_status':'completed','result_summary':'Local CLI adapter smoke completed.',"
        "'artifacts':[]},'error':None,'metrics':{'elapsed_ms':1,'cost_usd':0.0,"
        "'tokens_in':0,'tokens_out':0}}));"
    )
    return CliAdapterConfig(
        command=sys.executable,
        args=["-c", script],
        allowlist=[Path(sys.executable).name, sys.executable],
        timeout_ms=30_000,
    )


def _string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"Field '{field_name}' must be a list")
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Field '{field_name}' item {index} must be a non-empty string")
        result.append(item)
    return result


def _string_dict(value: Any, field_name: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"Field '{field_name}' must be a table")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError(f"Field '{field_name}' must contain string keys and values")
        result[key] = item
    return result
