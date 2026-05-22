# Task: Benchmark read-only config understanding

## Metadata

- Schema: task_spec.v0
- Task ID: bench-readonly-config-report
- Phase: Benchmark
- Slice: Read-only Config Understanding
- Owner: commander

## Objective

Inspect the agent-bridge configuration files and report how OpenCode, nanoGPT, and Antigravity adapters are wired. Focus on concrete agent IDs, runner IDs, model/provider fields, and safety-relevant env flags.

## Allowed Files

- config/agents.toml
- config/runners.toml
- .agent/tasks/bench_readonly_config_report.toml
- .agent/tasks/bench_readonly_config_report.md

## Forbidden Files

- docs/plan/agent_bridge_mvp.md
- .git/**
- .agent/runs/**
- .agent/metrics/**
- .agent/sessions/*.json

## Required Commands

- uv run agent-bridge task validate --spec .agent/tasks/bench_readonly_config_report.toml
- uv run agent-bridge task render --spec .agent/tasks/bench_readonly_config_report.toml --out .agent/tasks/bench_readonly_config_report.md
- uv run agent-bridge run --agent opencode_kimi_report --task .agent/tasks/bench_readonly_config_report.md --workspace .
- uv run agent-bridge task check-tool-use --spec .agent/tasks/bench_readonly_config_report.toml --run latest --workspace .

## Acceptance Criteria

- The report identifies opencode_kimi_readonly, opencode_kimi_report, and antigravity_smoke if present.
- The report distinguishes model/provider config from runner env config.
- The report mentions --pure or AGENT_BRIDGE_OPENCODE_PURE when present.
- The report does not inspect files outside the allowed config files.

## Hard Rules

- Do not commit.
- Do not implement the next phase.
- Do not modify files.
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
