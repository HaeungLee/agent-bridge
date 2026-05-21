# Task: Benchmark read-only gate understanding

## Metadata

- Schema: task_spec.v0
- Task ID: bench-readonly-gate-report
- Phase: Benchmark
- Slice: Read-only Gate Understanding
- Owner: commander

## Objective

Inspect the task specification and CLI gate code. Report how task_spec.v0 validation, git result checking, and raw JSONL tool-use path checking protect scope before write-capable adapters are enabled.

## Allowed Files

- src/agent_bridge/task_spec.py
- src/agent_bridge/cli.py
- .agent/tasks/phase5b_tool_use_path_checker.toml
- .agent/tasks/bench_readonly_gate_report.toml
- .agent/tasks/bench_readonly_gate_report.md

## Forbidden Files

- agent_bridge_mvp.md
- .git/**
- .agent/runs/**
- .agent/metrics/**
- .agent/sessions/*.json

## Required Commands

- uv run agent-bridge task validate --spec .agent/tasks/bench_readonly_gate_report.toml
- uv run agent-bridge task render --spec .agent/tasks/bench_readonly_gate_report.toml --out .agent/tasks/bench_readonly_gate_report.md
- uv run agent-bridge run --agent opencode_kimi_report --task .agent/tasks/bench_readonly_gate_report.md --workspace .
- uv run agent-bridge task check-tool-use --spec .agent/tasks/bench_readonly_gate_report.toml --run latest --workspace .

## Acceptance Criteria

- The report distinguishes git changed-file checking from raw tool-use path checking.
- The report identifies the dataclasses used to return check results.
- The report states what kinds of violations cause failure.
- The report does not inspect files outside the allowed gate files.

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
