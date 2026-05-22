# Task: Run OpenCode read-only adapter smoke

## Metadata

- Schema: task_spec.v0
- Task ID: phase5b-opencode-readonly-smoke
- Phase: Phase 5
- Slice: OpenCode CLI Adapter Smoke
- Owner: commander

## Objective

Verify that agent-bridge can invoke OpenCode through a cli_adapter shim in read-only/report-only mode, capture raw stdout/stderr, produce normalized run artifacts, and keep repository changes within the declared task scope.

## Allowed Files

- config/agents.toml
- config/runners.toml
- .gitignore
- src/agent_bridge/cli.py
- src/agent_bridge/runs.py
- src/agent_bridge/runners/base.py
- src/agent_bridge/runners/cli_adapter.py
- src/agent_bridge/adapters/__init__.py
- src/agent_bridge/adapters/opencode_readonly.py
- .agent/tasks/phase5b_opencode_readonly_smoke.toml
- .agent/tasks/phase5b_opencode_readonly_smoke.md
- docs/process/20260521_process.md
- docs/plan/roadmap.md

## Forbidden Files

- docs/plan/agent_bridge_mvp.md
- .git/**
- .agent/runs/**
- .agent/metrics/**
- .agent/sessions/*.json

## Required Commands

- opencode --version
- oh-my-openagent --version
- uv run agent-bridge task validate --spec .agent/tasks/phase5b_opencode_readonly_smoke.toml
- uv run agent-bridge task render --spec .agent/tasks/phase5b_opencode_readonly_smoke.toml --out .agent/tasks/phase5b_opencode_readonly_smoke.md
- uv run agent-bridge run --agent opencode_kimi_readonly --task .agent/tasks/phase5b_opencode_readonly_smoke.md --workspace .
- uv run agent-bridge summarize --run latest
- uv run agent-bridge task check-result --spec .agent/tasks/phase5b_opencode_readonly_smoke.toml --workspace .
- uv run agent-bridge doctor

## Acceptance Criteria

- OpenCode is invoked through cli_adapter using shell=False.
- The task prompt is delivered to the adapter and then to OpenCode.
- Successful smoke requires OpenCode text output containing AGENT_BRIDGE_OPENCODE_SMOKE_OK.
- Run artifacts include decision_report.json, raw/stdout.txt, raw/stderr.txt, and completed.marker.
- OpenCode session_id is captured and stored under .agent/sessions for continue_named policy.
- The adapter remains read-only and does not intentionally modify repository files.
- nanoGPT/OpenCode model selection is configured through runner env/config, not hardcoded in runs.py.

## Hard Rules

- Do not commit.
- Do not implement the next phase.
- Do not enable write-capable OpenCode execution.
- Do not call APIs outside OpenCode's configured model invocation.
- Do not add runtime dependencies.

## Expected Report

- Changed files
- Commands run
- Result
- Risks
- Open questions
- Next recommended step

## Execution Boundary

Implement only the task described above. Do not implement future phases, adjacent features, or optional integrations.
If a required change appears to exceed the allowed files or hard rules, stop and report the blocker.
