# Task: Create latency classifier fixture

## Metadata

- Schema: task_spec.v0
- Task ID: bench-worktree-patch-latency-classifier
- Phase: Benchmark
- Slice: Aider Worktree Patch
- Owner: commander
- Execution Mode: worktree_patch

## Objective

Create one small Python fixture file for benchmarking subordinate patch quality.
Implement only `scratch/aider_patch_probe.py`.
The file must define `classify_runner_latency(seconds: float) -> str`.
Return exactly:
- "fast" when seconds < 30
- "moderate" when 30 <= seconds < 90
- "slow" when seconds >= 90
Raise `ValueError("seconds must be non-negative")` for negative input.
Include a module docstring and a concise function docstring.
Do not add tests, imports, comments, or any other files.

## Allowed Files

- scratch/aider_patch_probe.py

## Read Scope

- scratch/aider_patch_probe.py

## Write Scope

- scratch/aider_patch_probe.py

## Expected Artifacts

- summary.md
- decision_report.json
- diffstat.txt
- touched_files.json
- tests.md
- risks.md
- process.md
- metrics.json
- request.json
- completed.marker
- raw/stdout.txt
- raw/stderr.txt
- patch.diff
- worktree.json

## Forbidden Files

- .git/**
- .agent/runs/**
- .agent/metrics/**
- .agent/sessions/*.json
- docs/plan/agent_bridge_mvp.md
- config/**
- src/**
- test/**
- docs/**

## Required Commands

- uv run agent-bridge task validate --spec .agent/tasks/bench_worktree_patch_latency_classifier.toml
- uv run agent-bridge task render --spec .agent/tasks/bench_worktree_patch_latency_classifier.toml --out .agent/tasks/bench_worktree_patch_latency_classifier.md
- uv run agent-bridge run --agent <agent> --task .agent/tasks/bench_worktree_patch_latency_classifier.md --workspace .
- uv run agent-bridge task gate --spec .agent/tasks/bench_worktree_patch_latency_classifier.toml --run <run-id> --workspace .

## Acceptance Criteria

- Only scratch/aider_patch_probe.py is changed.
- The patch creates classify_runner_latency(seconds: float) -> str.
- The function returns fast, moderate, and slow using the exact thresholds in the objective.
- The function raises ValueError("seconds must be non-negative") for negative input.
- No commits are created.

## Hard Rules

- Do not commit.
- Do not implement the next phase.
- Do not modify files outside write_scope.
- Do not edit docs, config, src, test, .git, .agent/runs, .agent/metrics, or .agent/sessions.

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
