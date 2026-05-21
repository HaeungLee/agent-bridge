# CLI Runner Adapter 설계 문서

## 개요

이 문서는 Moonlight Rust 오케스트레이터(`W:\Projects\ProjectML\moonlight\packages\orchestrator`)의
`SubprocessExternalAdapterRunner` 구조를 분석하고, `agent-bridge` Python 환경에서
동일한 패턴으로 **OpenCode CLI**, **Antigravity CLI**, **GitHub Copilot CLI**, **Codex CLI** 등
외부 CLI 에이전트를 안전하게 호출하는 실 런너(Real Runner) 어댑터를 어떻게 구현할지 설명합니다.

**현재 위치**: Phase 5 준비 단계 - Moonlight 연결 이전의 자체 CLI 호출 계층 확보.

---

## 1. Moonlight 코드 분석 — 핵심 패턴

### 1.1 전체 호출 흐름

```
Commander (Python agent-bridge)
    │
    │  [1] AdapterRequestEnvelope (JSON 1줄, stdin)
    ▼
SubprocessExternalAdapterRunner
    │   ↳ command allowlist 검증
    │   ↳ subprocess.spawn() → stdin write → wait(timeout)
    │
    │  [2] stdout JSONL 읽기
    │   ↳ event 프레임* (0개 이상, 진행 상황)
    │   ↳ response 프레임 (최종 1개, 필수)
    ▼
AdapterDispatchCore → Commander가 결과 소비
```

### 1.2 계약 버전

```
ADAPTER_CONTRACT_VERSION = "adapter.v0.1"
```
모든 요청/이벤트/응답 봉투에 `contract` 필드로 포함됩니다.

### 1.3 AdapterRequestEnvelope (stdin에 1줄 JSON으로 전송)

```json
{
  "contract": "adapter.v0.1",
  "type": "request",
  "request_id": "uuid-v4-string",
  "method": "execute",
  "payload": {
    "plan_id": "plan-abc123",
    "execution": { "dry_run": false },
    "inputs": { "artifact_refs": [] }
  },
  "context": {
    "run_id": "run-xyz",
    "session_id": "sess-001",
    "user_id": "user-001",
    "policy_mode": "default",
    "deadline_ms": 30000,
    "budget": { "max_cost_usd": 0.5, "max_tokens": 50000 },
    "constraints": {
      "allow_network": false,
      "filesystem_scope": ["/workspace"],
      "risk_level": "low"
    },
    "trace": { "request_ts": "2026-05-21T13:00:00Z", "route_reason": "commander" }
  }
}
```

**6가지 메서드**: `health`, `capabilities`, `plan`, `execute`, `review`, `test`

### 1.4 AdapterStreamFrame — stdout에서 읽는 JSONL 라인들

**이벤트 프레임** (0개 이상, 선택적):
```json
{
  "contract": "adapter.v0.1",
  "type": "event",
  "request_id": "uuid-동일",
  "event": {
    "kind": "progress",
    "ts": "2026-05-21T13:00:01Z",
    "message": "Running tests...",
    "data": {}
  }
}
```

허용 이벤트 kind: `progress`, `log`, `artifact`, `warning`, `metric`,
또는 `x.<adapter_id>.<custom>` 네임스페이스.

**최종 응답 프레임** (필수 1개):
```json
{
  "contract": "adapter.v0.1",
  "type": "response",
  "request_id": "uuid-동일",
  "ok": true,
  "data": {
    "run_status": "completed",
    "result_summary": "...",
    "artifacts": []
  },
  "error": null,
  "metrics": {
    "elapsed_ms": 5200,
    "cost_usd": 0.012,
    "tokens_in": 1200,
    "tokens_out": 800
  }
}
```

`run_status` 허용값: `completed`, `partial`, `failed`, `needs_approval`, `blocked`

### 1.5 Rust에서의 보안/안전 규칙 (Python에서도 동일 적용 필요)

| 규칙 | Rust 구현 위치 | 설명 |
|---|---|---|
| 명령어 allowlist | `is_command_allowlisted()` | basename 또는 full path 일치 검증 |
| stdin 크기 제한 | `MAX_JSONL_LINE_BYTES = 64KB` | 요청 JSON이 64KB 초과 시 거부 |
| stdout 라인 제한 | `MAX_JSONL_LINE_BYTES = 64KB` | 각 출력 라인, response는 512KB |
| timeout + kill 시퀀스 | `invoke_once()` | timeout → graceful SIGTERM → 1.5s → SIGKILL |
| shell=False 강제 | `Command::new()` | shell injection 원천 차단 |
| exit code 검증 | `parse_stdout_lines()` | `ok=true`인데 exit code != 0이면 오류 |

---

## 2. Python 변환 설계

### 2.1 새 파일 구조

```
src/agent_bridge/runners/
├── __init__.py          (기존)
├── base.py              (기존 RunnerResult, Runner ABC)
├── mock_subprocess.py   (기존)
└── cli_adapter.py       [NEW] ← 이 문서의 핵심 구현 대상
```

`config/agents.toml`에 CLI 에이전트 등록, `config/runners.toml`에 CLI 러너 설정 추가.

### 2.2 `cli_adapter.py` — 핵심 구현 스펙

```python
# src/agent_bridge/runners/cli_adapter.py
"""
CliAdapterRunner: Moonlight adapter.v0.1 계약을 따르는
외부 CLI 프로세스(opencode, antigravity, codex, copilot 등)를
안전하게 subprocess로 호출하는 러너 어댑터.
"""

import json
import subprocess
import uuid
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent_bridge.runners.base import Runner, RunnerResult

ADAPTER_CONTRACT_VERSION = "adapter.v0.1"
MAX_REQUEST_BYTES = 64 * 1024          # 64KB
MAX_RESPONSE_LINE_BYTES = 512 * 1024   # 512KB
MAX_EVENT_LINE_BYTES = 64 * 1024       # 64KB
STDERR_PREVIEW_CHARS = 1024

ALLOWED_RUN_STATUS = {"completed", "partial", "failed", "needs_approval", "blocked"}
ALLOWED_EVENT_KINDS = {"progress", "log", "artifact", "warning", "metric"}
```

#### 2.2.1 `AdapterInvoker` 클래스

```python
@dataclass
class CliAdapterConfig:
    command: str                          # 실행할 CLI 명령어 (예: "opencode", "antigravity")
    args: list[str] = field(default_factory=list)
    allowlist: list[str] = field(default_factory=list)  # 빈 경우 command 자체가 허용
    timeout_ms: int = 30_000
    max_retries: int = 0
    env: dict[str, str] = field(default_factory=dict)

class CliAdapterRunner(Runner):
    """
    Moonlight SubprocessExternalAdapterRunner의 Python 포트.
    외부 CLI 에이전트를 adapter.v0.1 계약으로 호출합니다.
    """

    def __init__(self, adapter_id: str, config: CliAdapterConfig):
        self.adapter_id = adapter_id
        self.command = config.command.strip()
        self.args = config.args
        self.allowlist = set(
            e.strip() for e in (config.allowlist or [self.command]) if e.strip()
        )
        self.timeout_ms = max(config.timeout_ms, 1)
        self.max_retries = config.max_retries
        self.env = config.env
```

#### 2.2.2 allowlist 검증

```python
    def _is_command_allowlisted(self) -> bool:
        """Rust의 is_command_allowlisted() 동일 로직"""
        if not self.command:
            return False
        if self.command in self.allowlist:
            return True
        basename = Path(self.command).name
        return basename in self.allowlist
```

#### 2.2.3 요청 봉투 생성

```python
    def _build_request_envelope(
        self,
        method: str,       # "health" | "capabilities" | "plan" | "execute" | "review" | "test"
        payload: dict,
        run_id: str = "",
        workspace_path: str = "",
        task_content: str = "",
    ) -> dict:
        """AdapterRequestEnvelope 생성"""
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
                "deadline_ms": self.timeout_ms,
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
```

#### 2.2.4 subprocess 호출 — 핵심

```python
    def _invoke_once(self, request_envelope: dict) -> tuple[list[dict], dict]:
        """
        Rust의 invoke_once()에 해당.
        stdin에 JSON 1줄 전송 → stdout JSONL 파싱.

        Returns:
            (events, final_response) 튜플.
        Raises:
            RuntimeError: 계약 위반, timeout, process 오류 등.
        """
        request_line = json.dumps(request_envelope, ensure_ascii=False)
        request_bytes = request_line.encode("utf-8")
        if len(request_bytes) > MAX_REQUEST_BYTES:
            raise RuntimeError(
                f"request_too_large: {len(request_bytes)} bytes > {MAX_REQUEST_BYTES}"
            )

        import os
        env = {**os.environ, **self.env}

        # shell=False 강제 — shell injection 차단
        cmd = [self.command] + self.args
        try:
            result = subprocess.run(
                cmd,
                input=request_bytes,
                capture_output=True,
                timeout=self.timeout_ms / 1000.0,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            stderr_preview = _stderr_preview(
                (exc.stderr or b"").decode("utf-8", errors="replace")
            )
            raise RuntimeError(
                f"timeout: adapter timed out after {self.timeout_ms}ms. "
                f"stderr: {stderr_preview}"
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"adapter_unavailable: command not found: {self.command!r}"
            )

        stdout = result.stdout.decode("utf-8", errors="strict")
        stderr = result.stderr.decode("utf-8", errors="replace")

        events, final_response = _parse_stdout_lines(
            request_id=request_envelope["request_id"],
            adapter_id=self.adapter_id,
            stdout=stdout,
            stderr=stderr,
            exit_code=result.returncode,
        )
        return events, final_response
```

#### 2.2.5 stdout JSONL 파싱

```python
def _parse_stdout_lines(
    request_id: str,
    adapter_id: str,
    stdout: str,
    stderr: str,
    exit_code: int,
) -> tuple[list[dict], dict]:
    """
    Rust의 parse_stdout_lines() 에 해당.
    JSONL 라인을 순서대로 파싱하여 events/response로 분리.
    """
    lines = [
        line.rstrip("\r")
        for line in stdout.splitlines()
        if line.strip()
    ]

    events = []
    final_response = None

    for i, line in enumerate(lines):
        line_bytes = len(line.encode("utf-8"))

        # event는 64KB, response는 512KB 제한
        if line_bytes > MAX_EVENT_LINE_BYTES:
            raise RuntimeError(
                f"adapter_failure: line {i} exceeds 64KB ({line_bytes} bytes)"
            )

        try:
            frame = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"adapter_failure: invalid JSON at line {i}: {exc}")

        frame_type = frame.get("type")

        if frame_type == "event":
            _validate_event(frame, request_id, adapter_id, i)
            events.append(frame)

        elif frame_type == "response":
            if final_response is not None:
                raise RuntimeError(
                    f"adapter_failure: multiple response frames (duplicate at line {i})"
                )
            if line_bytes > MAX_RESPONSE_LINE_BYTES:
                raise RuntimeError(
                    f"adapter_failure: response line {i} exceeds 512KB"
                )
            _validate_response(frame, request_id, i)
            final_response = frame

        else:
            raise RuntimeError(
                f"adapter_failure: unsupported frame type {frame_type!r} at line {i}"
            )

    if final_response is None:
        preview = _stderr_preview(stderr)
        raise RuntimeError(
            f"adapter_failure: no final response frame emitted. "
            f"exit_code={exit_code}, stderr={preview}"
        )

    # ok=true인데 exit code != 0이면 오류 (Rust 동일 규칙)
    if final_response.get("ok") and exit_code != 0:
        raise RuntimeError(
            f"adapter_failure: ok=true but non-zero exit code {exit_code}"
        )

    return events, final_response
```

#### 2.2.6 검증 헬퍼

```python
def _validate_event(frame: dict, request_id: str, adapter_id: str, idx: int):
    if frame.get("contract") != ADAPTER_CONTRACT_VERSION:
        raise RuntimeError(
            f"event contract mismatch at line {idx}: "
            f"expected {ADAPTER_CONTRACT_VERSION!r}, got {frame.get('contract')!r}"
        )
    if frame.get("request_id") != request_id:
        raise RuntimeError(f"event request_id mismatch at line {idx}")
    kind = frame.get("event", {}).get("kind", "")
    if not _is_allowed_event_kind(kind, adapter_id):
        raise RuntimeError(
            f"event kind {kind!r} not allowed for adapter {adapter_id!r} at line {idx}. "
            f"Use 'x.{adapter_id}.<kind>' namespace for custom events."
        )

def _validate_response(frame: dict, request_id: str, idx: int):
    if frame.get("contract") != ADAPTER_CONTRACT_VERSION:
        raise RuntimeError(
            f"response contract mismatch at line {idx}: "
            f"expected {ADAPTER_CONTRACT_VERSION!r}, got {frame.get('contract')!r}"
        )
    if frame.get("request_id") != request_id:
        raise RuntimeError(f"response request_id mismatch at line {idx}")

def _is_allowed_event_kind(kind: str, adapter_id: str) -> bool:
    if kind in ALLOWED_EVENT_KINDS:
        return True
    prefix = f"x.{adapter_id}."
    return kind.startswith(prefix) and len(kind) > len(prefix)

def _stderr_preview(stderr: str) -> str:
    trimmed = stderr.strip()
    if not trimmed:
        return ""
    preview = trimmed[:STDERR_PREVIEW_CHARS]
    if len(trimmed) > STDERR_PREVIEW_CHARS:
        preview += "..."
    return preview
```

---

## 3. agents.toml / runners.toml 등록 방식

### `config/agents.toml` — CLI 에이전트 등록 예시

```toml
[agents.opencode_impl]
model     = "opencode-latest"
provider  = "local"
runner    = "cli_subprocess"
role      = "implementation"
mode      = "execute"

[agents.antigravity_review]
model     = "antigravity-latest"
provider  = "local"
runner    = "cli_subprocess"
role      = "code_review"
mode      = "review"

[agents.codex_investigate]
model     = "codex-cli"
provider  = "openai-local"
runner    = "cli_subprocess"
role      = "investigation"
mode      = "plan"
```

### `config/runners.toml` — 러너별 CLI 명령어 매핑

```toml
[runners.cli_subprocess]
type        = "cli_adapter"       # CliAdapterRunner 선택자

# 어댑터별 command 설정
[runners.cli_subprocess.adapters.opencode_impl]
command     = "opencode"          # PATH에서 탐색 또는 절대 경로
args        = ["run", "--adapter-mode"]
allowlist   = ["opencode"]
timeout_ms  = 120000
max_retries = 1
env         = {}

[runners.cli_subprocess.adapters.antigravity_review]
command     = "antigravity"
args        = []
allowlist   = ["antigravity"]
timeout_ms  = 60000
max_retries = 0
env         = {}

[runners.cli_subprocess.adapters.codex_investigate]
command     = "codex"
args        = []
allowlist   = ["codex"]
timeout_ms  = 90000
max_retries = 0
env         = {}
```

---

## 4. `agent-bridge run` 흐름 — 실 CLI 호출 시나리오

```
agent-bridge run --agent opencode_impl --task .agent/tasks/impl_phase5.md --workspace .
    │
    │  [1] config/agents.toml에서 opencode_impl → runner=cli_subprocess 확인
    │  [2] config/runners.toml에서 cli_subprocess.adapters.opencode_impl 로드
    │  [3] CliAdapterRunner(adapter_id="opencode_impl", config) 인스턴스 생성
    │  [4] task 파일 내용 읽기 → payload.task_prompt에 포함
    │
    │  [5] health 메서드로 어댑터 상태 확인 (선택적)
    │  [6] capabilities 메서드로 지원 기능 확인 (선택적)
    │  [7] plan 메서드 → plan_id 획득
    │  [8] execute 메서드(plan_id 포함) → 실행 스트림
    │
    │  stdin → opencode run --adapter-mode
    │  stdout ← JSONL event/response 프레임
    │
    ▼
.agent/runs/<run_id>/
├── request.json          (AdapterRequestEnvelope 기록)
├── decision_report.json  (AdapterResponseEnvelope → 변환)
├── summary.md
├── metrics.json          (AdapterMetrics 포함)
├── raw/stdout.txt        (원본 JSONL 스트림)
└── raw/stderr.txt
```

---

## 5. execute payload 설계 — task 정보 전달

외부 CLI가 실제 작업 내용을 받아야 합니다. `payload`에 다음 필드를 포함합니다:

```json
{
  "plan_id": "plan-<run_id>",
  "task_prompt": "<.agent/tasks/*.md 파일 전체 내용>",
  "workspace_path": "/absolute/path/to/workspace",
  "execution": {
    "dry_run": false,
    "require_approval": false
  },
  "inputs": {
    "artifact_refs": []
  }
}
```

> **중요**: `plan_id`는 외부 subprocess 어댑터에서 필수입니다 (Moonlight conformance 규칙).
> `plan_id`가 없으면 `validation_failed` 오류로 거부합니다.

---

## 6. CLI가 준수해야 할 어댑터 계약 (adapter-side 구현 가이드)

opencode, antigravity 등 CLI 도구가 `adapter.v0.1` 계약을 준수하려면:

1. **stdin에서 JSON 1줄 읽기** — 파싱 후 `method` 필드로 분기
2. **stdout에 JSONL 출력**:
   - 진행 상황: `{"type":"event", ...}` 라인 (선택)
   - 최종 응답: `{"type":"response", ...}` 라인 (필수 1개)
3. **exit code**: 성공 시 `0`, 실패 시 `0`이 아닌 값 + `ok: false` 응답
4. **request_id 에코**: 모든 출력 프레임의 `request_id`를 입력과 동일하게 유지
5. **contract 버전 필드**: `"adapter.v0.1"` 하드코딩

### 최소 health 응답 예시 (bash/python wrapper)

```bash
#!/usr/bin/env bash
# minimal_adapter.sh — adapter.v0.1 minimal conformance example
read -r request_json
method=$(echo "$request_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['method'])")
req_id=$(echo "$request_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['request_id'])")

case "$method" in
  health)
    echo "{\"contract\":\"adapter.v0.1\",\"type\":\"response\",\"request_id\":\"$req_id\",\"ok\":true,\"data\":{\"status\":\"ready\"},\"metrics\":{\"elapsed_ms\":1}}"
    ;;
  execute)
    echo "{\"contract\":\"adapter.v0.1\",\"type\":\"event\",\"request_id\":\"$req_id\",\"event\":{\"kind\":\"progress\",\"ts\":\"$(date -u +%FT%TZ)\",\"message\":\"starting\",\"data\":{}}}"
    echo "{\"contract\":\"adapter.v0.1\",\"type\":\"response\",\"request_id\":\"$req_id\",\"ok\":true,\"data\":{\"run_status\":\"completed\"},\"metrics\":{\"elapsed_ms\":500}}"
    ;;
esac
```

---

## 7. Python에서의 구현 순서 (Phase 5 실행 계획)

| 단계 | 작업 | 파일 |
|---|---|---|
| 1 | `CliAdapterConfig` 데이터클래스 정의 | `runners/cli_adapter.py` |
| 2 | `CliAdapterRunner` 클래스 — allowlist + subprocess 호출 | `runners/cli_adapter.py` |
| 3 | JSONL 파싱 함수 (`_parse_stdout_lines`) | `runners/cli_adapter.py` |
| 4 | `runs.py`에서 runner 타입 `cli_adapter` 분기 추가 | `runs.py` |
| 5 | `config.py`에서 `runners.toml` adapter 설정 로드 | `config.py` |
| 6 | `config/runners.toml`에 CLI 어댑터 항목 추가 | `config/runners.toml` |
| 7 | `config/agents.toml`에 `opencode_impl` 등 등록 | `config/agents.toml` |
| 8 | `doctor` 명령에 CLI 명령어 존재 여부 체크 추가 | `cli.py` |
| 9 | E2E 테스트: `health` → `capabilities` → `execute` | 로컬 검증 |

---

## 8. 보안 원칙 (Moonlight와 동일)

- **allowlist 필수**: TOML에 명시적으로 등록된 명령어만 실행 가능
- **shell=False**: `subprocess.run(cmd_list, ...)` — 절대 `shell=True` 금지
- **timeout 강제**: 기본 30초, TOML에서 구성
- **stdin 크기 제한**: 64KB 초과 요청 거부
- **exit code 검증**: `ok=true` 응답인데 exit code != 0이면 오류 처리
- **환경 변수 격리**: TOML `env` 블록에 명시된 것만 추가로 주입

---

## 9. 참고 파일 (Moonlight 소스)

| Moonlight 파일 | 역할 | Python 대응 |
|---|---|---|
| `adapter_runtime/types.rs` | 계약 타입 정의 | 위 dict 스키마 |
| `adapter_runtime/subprocess_runner.rs` | 핵심 subprocess 호출 | `CliAdapterRunner` |
| `adapter_runtime/dispatch.rs` | 메서드 라우팅, allowlist | `CliAdapterRunner._dispatch()` |
| `adapter_runtime/registry.rs` | 어댑터 등록 관리 | `config/agents.toml` |
| `adapter_runtime/conformance.rs` | C1 적합성 검사 | `agent-bridge doctor` 확장 |

---

*최종 수정: 2026-05-21*
*작성 기준: Moonlight orchestrator commit 분석 (tag: phase-S)*
