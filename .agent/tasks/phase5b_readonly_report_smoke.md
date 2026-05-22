# Task: Run a small read-only repository report through OpenCode

## Metadata

- Schema: task_spec.v0
- Task ID: phase5b-readonly-report-smoke
- Phase: Phase 5
- Slice: OpenCode Readonly Report
- Owner: commander

## Objective

Verify that the dedicated OpenCode readonly report agent can inspect a small, explicit repository scope and return a compact factual report without modifying files.

## Allowed Files

- config/agents.toml
- config/runners.toml
- src/agent_bridge/adapters/opencode_readonly.py
- .opencode/agent/agents/bridge-readonly-report.md
- .agent/tasks/phase5b_readonly_report_smoke.toml
- .agent/tasks/phase5b_readonly_report_smoke.md
- docs/process/20260521_process.md
- docs/plan/roadmap.md

## Forbidden Files

- docs/plan/agent_bridge_mvp.md
- .git/**
- .agent/runs/**
- .agent/metrics/**
- .agent/sessions/*.json

## Required Commands

- uv run agent-bridge task validate --spec .agent/tasks/phase5b_readonly_report_smoke.toml
- uv run agent-bridge task render --spec .agent/tasks/phase5b_readonly_report_smoke.toml --out .agent/tasks/phase5b_readonly_report_smoke.md
- uv run agent-bridge run --agent opencode_kimi_report --task .agent/tasks/phase5b_readonly_report_smoke.md --workspace .
- uv run agent-bridge summarize --run latest
- uv run agent-bridge task check-result --spec .agent/tasks/phase5b_readonly_report_smoke.toml --workspace .

## Acceptance Criteria

- OpenCode is invoked with --pure and agents/bridge-readonly-report.
- The run completes with normalized artifacts.
- The agent produces a compact factual report about OpenCode-related config in config/agents.toml and config/runners.toml.
- No repository files are modified by the OpenCode report run.
- Session metadata is recorded in metrics.json.

## Hard Rules

- Do not commit.
- Do not implement the next phase.
- Do not enable write-capable OpenCode execution.
- Do not modify files during the OpenCode report run.
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
