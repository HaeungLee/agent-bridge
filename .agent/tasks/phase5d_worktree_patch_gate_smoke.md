# Task: Smoke test worktree patch gate

## Metadata

- Schema: task_spec.v0
- Task ID: phase5d-worktree-patch-gate-smoke
- Phase: Phase 5-D
- Slice: Worktree Patch Gate Foundation
- Owner: commander
- Execution Mode: worktree_patch

## Objective

Verify that task_spec.v0 worktree_patch mode can validate patch.diff and worktree.json artifacts against write_scope and forbidden_files without using active workspace git status.

## Allowed Files

- src/agent_bridge/task_spec.py

## Read Scope

- src/agent_bridge/task_spec.py

## Write Scope

- src/agent_bridge/task_spec.py

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

## Forbidden Files

- .git/**
- .agent/runs/**
- .agent/metrics/**
- .agent/sessions/*.json
- docs/plan/agent_bridge_mvp.md

## Required Commands

- uv run agent-bridge task validate --spec .agent/tasks/phase5d_worktree_patch_gate_smoke.toml
- uv run agent-bridge task check-patch --spec .agent/tasks/phase5d_worktree_patch_gate_smoke.toml --run <synthetic-run>

## Acceptance Criteria

- worktree_patch mode requires patch.diff and worktree.json.
- patch.diff changed paths are validated against write_scope.
- patch.diff changed paths are validated against forbidden_files.
- worktree.json run_id must match the run directory name.

## Hard Rules

- Do not commit.
- Do not implement the next phase.
- Do not modify active workspace files as part of this smoke.

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
