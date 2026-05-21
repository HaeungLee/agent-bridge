# Adapter Contract and CLI Runner Design

Date: 2026-05-21

Status: design draft for Phase 5 runner work.

Purpose: define how `agent-bridge` should call real CLI-based coding agents such as OpenCode, Codex CLI, Gemini CLI, Copilot CLI, or future Antigravity automation surfaces, while preserving Moonlight-compatible adapter concepts.

## 1. Design Goal

The runner layer should let the commander call external coding tools through one stable contract:

```text
agent-bridge run
  -> load agent config
  -> load runner config
  -> build adapter request
  -> invoke CLI with shell=False
  -> capture stdout/stderr
  -> parse normalized response
  -> write run artifacts
  -> write completed.marker last
```

The first real target should be OpenCode because it is open-source and can be wrapped as a CLI runner. nanoGPT models can then be used through OpenCode or an OpenAI-compatible provider configuration.

Raw API access should remain a separate report-only runner. API-only models do not naturally inspect a workspace unless the bridge spends tokens packaging context for them.

## 2. Contract Version

Use a Moonlight-aligned adapter contract:

```text
adapter.v0.1
```

Every request, event, and response frame must include:

```json
{
  "contract": "adapter.v0.1",
  "type": "request|event|response",
  "request_id": "uuid"
}
```

## 3. Request Envelope

The bridge sends one JSON request to the runner through stdin.

Minimal shape:

```json
{
  "contract": "adapter.v0.1",
  "type": "request",
  "request_id": "uuid",
  "method": "execute",
  "payload": {
    "plan_id": "plan-<run_id>",
    "task_prompt": "<task.md contents>",
    "workspace_path": "<absolute workspace path>",
    "execution": {
      "dry_run": false,
      "require_approval": false
    },
    "inputs": {
      "artifact_refs": []
    }
  },
  "context": {
    "run_id": "<run_id>",
    "session_id": "",
    "user_id": "commander",
    "policy_mode": "default",
    "deadline_ms": 30000,
    "budget": {
      "max_cost_usd": 0.0,
      "max_tokens": 0
    },
    "constraints": {
      "allow_network": false,
      "filesystem_scope": ["<workspace path>"],
      "risk_level": "low"
    },
    "trace": {
      "request_ts": "<utc iso timestamp>",
      "route_reason": "agent-bridge-commander"
    }
  }
}
```

Supported methods:

```text
health
capabilities
plan
execute
review
test
```

Phase 5 should implement only enough for `execute` against a mock adapter or OpenCode-compatible shim. Do not integrate every method at once.

## 4. Output Frames

The runner writes JSONL frames to stdout.

Event frame:

```json
{
  "contract": "adapter.v0.1",
  "type": "event",
  "request_id": "same request id",
  "event": {
    "kind": "progress",
    "ts": "utc iso timestamp",
    "message": "running",
    "data": {}
  }
}
```

Final response frame:

```json
{
  "contract": "adapter.v0.1",
  "type": "response",
  "request_id": "same request id",
  "ok": true,
  "data": {
    "run_status": "completed",
    "result_summary": "short summary",
    "artifacts": []
  },
  "error": null,
  "metrics": {
    "elapsed_ms": 1000,
    "cost_usd": 0.0,
    "tokens_in": 0,
    "tokens_out": 0
  }
}
```

Allowed run statuses:

```text
completed
partial
failed
needs_approval
blocked
```

Allowed event kinds:

```text
progress
log
artifact
warning
metric
x.<adapter_id>.<custom>
```

Exactly one final response frame is required.

## 5. Security Rules

Phase 5 CLI runner must follow these rules:

- Use `subprocess.run([...], shell=False)`.
- Use explicit command allowlists.
- Never execute arbitrary user-provided command strings.
- Limit request JSON size to 64 KiB initially.
- Limit event JSONL line size to 64 KiB.
- Limit final response line size to 512 KiB.
- Enforce timeout.
- Treat `ok=true` with non-zero exit code as an adapter failure.
- Preserve raw stdout and stderr under the run directory.
- Do not print secrets.
- Do not pass the entire environment blindly once real providers are enabled; use explicit env allow/overlay.

## 6. Proposed Files

Add:

```text
src/agent_bridge/runners/cli_adapter.py
```

Keep existing:

```text
src/agent_bridge/runners/base.py
src/agent_bridge/runners/mock_subprocess.py
```

Do not create OpenCode-specific implementation first. Implement a generic `CliAdapterRunner`, then configure OpenCode as one adapter entry.

## 7. Config Shape

Agents choose a runner:

```toml
[agents.opencode_impl]
runner = "cli_adapter"
provider = "nanogpt"
model = "kimi-k2.6"
role = "implementation"
default_mode = "execute"
max_cost_usd = 2.0
output_contract = "adapter.v0.1"
adapter_id = "opencode_impl"
```

Runner config maps adapter IDs to commands:

```toml
[runners.cli_adapter]
type = "cli_adapter"

[runners.cli_adapter.adapters.opencode_impl]
command = "opencode"
args = ["run", "--adapter-mode"]
allowlist = ["opencode"]
timeout_ms = 120000
max_retries = 0

[runners.cli_adapter.adapters.codex_review]
command = "codex"
args = []
allowlist = ["codex"]
timeout_ms = 90000
max_retries = 0
```

For nanoGPT, provider/model selection should be passed through environment/config expected by the target CLI. Do not hardcode nanoGPT into the generic CLI runner.

## 8. Runner Result Mapping

`CliAdapterRunner` should return the existing `RunnerResult`:

```text
status          <- response.data.run_status mapped to completed/failed/blocked/timeout
exit_code       <- subprocess return code
stdout          <- raw stdout
stderr          <- raw stderr
summary         <- response.data.result_summary or error message
commands_run    <- display command only, not secrets
runtime_seconds <- measured elapsed time
```

The higher-level run writer remains responsible for:

- `decision_report.json`
- `summary.md`
- `metrics.json`
- `raw/stdout.txt`
- `raw/stderr.txt`
- `completed.marker`

## 9. Phase 5-A Implementation Slice

Keep the first implementation small.

Implement:

- `CliAdapterConfig`
- `CliAdapterRunner`
- command allowlist check
- request envelope builder
- subprocess invocation with stdin JSON
- JSONL parser
- event/response validation
- timeout handling
- error normalization into `RunnerResult`

Do not implement:

- real OpenCode task execution
- Antigravity
- patch generation
- temp worktrees
- retries
- provider-specific env resolution
- health/capabilities flows beyond optional smoke tests

## 10. Phase 5-B Smoke Adapter

Before calling OpenCode, create a tiny local adapter script or Python `-c` shim that:

- reads one JSON request line from stdin
- emits one event frame
- emits one response frame
- exits 0

This proves the adapter contract without depending on OpenCode.

Only after this passes should OpenCode be configured as a real adapter.

## 11. Doctor Extensions

Later, `agent-bridge doctor` should warn for:

- configured CLI command not found on PATH
- command not in allowlist
- missing expected provider env vars
- timeout value missing or too small
- adapter config missing for an agent's `adapter_id`

Warnings are enough until real external runners become mandatory.

## 12. Open Questions

- Should CLI adapters consume `adapter.v0.1` directly, or should agent-bridge wrap tools that do not understand the contract?
- Should OpenCode be invoked in a temporary worktree from day one?
- Should provider/model be set through environment variables, command args, or a generated OpenCode config file?
- Should `model_routing.md` remain tracked or move to a sample/generated artifact split?

## 13. Recommended Next Step

Implement Phase 5-A with a local contract smoke adapter first.

Suggested task:

```text
Implement `src/agent_bridge/runners/cli_adapter.py` and a local adapter contract smoke test.
Do not integrate OpenCode yet.
Do not call nanoGPT yet.
Do not implement worktrees or patch generation.
```
