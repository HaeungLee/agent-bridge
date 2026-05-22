# Task: Design model benchmark matrix

## Metadata

- Schema: task_spec.v0
- Task ID: bench-model-matrix-report
- Phase: Benchmark
- Slice: Model Comparison Design
- Owner: commander

## Objective

Design a compact benchmark matrix for comparing Kimi k2.6, DeepSeek v4 Flash, DeepSeek v4 Pro, Mimo v2.5 Pro, and Gemini/Antigravity. Use the existing three read-only benchmark specs and propose one write-capable dry-run benchmark that can run only in an isolated worktree. Focus on measurement fields, commands, and evaluation criteria.

## Allowed Files

- docs/commander_handbook.md
- docs/model_observations.md
- .agent/tasks/bench_readonly_config_report.toml
- .agent/tasks/bench_readonly_runner_flow_report.toml
- .agent/tasks/bench_readonly_gate_report.toml
- .agent/tasks/bench_model_matrix_report.toml
- .agent/tasks/bench_model_matrix_report.md
- docs/process/20260522_process.md

## Forbidden Files

- docs/plan/agent_bridge_mvp.md
- .git/**
- .agent/runs/**
- .agent/metrics/**
- .agent/sessions/*.json

## Required Commands

- uv run agent-bridge task validate --spec .agent/tasks/bench_model_matrix_report.toml
- uv run agent-bridge task render --spec .agent/tasks/bench_model_matrix_report.toml --out .agent/tasks/bench_model_matrix_report.md

## Acceptance Criteria

- Report a benchmark matrix for the listed models.
- Reuse the three existing read-only benchmark specs.
- Propose one write-capable dry-run benchmark gated by isolated worktree execution.
- Define evaluation fields for scope discipline, artifact quality, code quality, verification, and instruction following.
- Do not modify files.

## Hard Rules

- Do not commit.
- Do not implement the next phase.
- Do not modify files.
- Do not self-declare Commander Verdict or PASS.

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
