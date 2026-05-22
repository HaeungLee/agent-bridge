# Task: Benchmark read-only runner flow understanding

## Metadata

- Schema: task_spec.v0
- Task ID: bench-readonly-runner-flow-report
- Phase: Benchmark
- Slice: Read-only Runner Flow Understanding
- Owner: commander

## Objective

Inspect the CLI adapter execution path and report the concrete flow from agent-bridge run to CliAdapterRunner to the OpenCode readonly adapter. Focus on shell=False, timeout handling, adapter response parsing, and where raw stdout/stderr artifacts are produced.

## Allowed Files

- src/agent_bridge/runs.py
- src/agent_bridge/runners/cli_adapter.py
- src/agent_bridge/adapters/opencode_readonly.py
- .agent/tasks/bench_readonly_runner_flow_report.toml
- .agent/tasks/bench_readonly_runner_flow_report.md

## Forbidden Files

- docs/plan/agent_bridge_mvp.md
- .git/**
- .agent/runs/**
- .agent/metrics/**
- .agent/sessions/*.json

## Required Commands

- uv run agent-bridge task validate --spec .agent/tasks/bench_readonly_runner_flow_report.toml
- uv run agent-bridge task render --spec .agent/tasks/bench_readonly_runner_flow_report.toml --out .agent/tasks/bench_readonly_runner_flow_report.md
- uv run agent-bridge run --agent opencode_kimi_report --task .agent/tasks/bench_readonly_runner_flow_report.md --workspace .
- uv run agent-bridge task check-tool-use --spec .agent/tasks/bench_readonly_runner_flow_report.toml --run latest --workspace .

## Acceptance Criteria

- The report names the key functions involved in CLI adapter execution.
- The report states whether subprocess calls use shell=False.
- The report explains how adapter JSONL response frames become RunnerResult metadata.
- The report does not inspect files outside the allowed source files.

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
