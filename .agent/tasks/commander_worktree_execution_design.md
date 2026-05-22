# Task: Design isolated git worktree execution

## Metadata

- Schema: task_spec.v0
- Task ID: commander-worktree-execution-design
- Phase: Phase 5 Follow-up
- Slice: Isolated Write Execution Design
- Owner: commander

## Objective

Review the current runner, task gate, and run artifact flow. Propose the smallest git worktree-based design for write-capable subordinate execution. Include CLI UX, run artifacts, patch export, cleanup policy, dirty active workspace policy, and failure modes. This is design-only.

## Allowed Files

- docs/commander_handbook.md
- docs/adapter_contract_and_cli_runner.md
- docs/task_spec_v0.md
- src/agent_bridge/runs.py
- src/agent_bridge/cli.py
- src/agent_bridge/task_spec.py
- src/agent_bridge/runners/cli_adapter.py
- src/agent_bridge/adapters/opencode_readonly.py
- config/agents.toml
- config/runners.toml
- .agent/tasks/commander_worktree_execution_design.toml
- .agent/tasks/commander_worktree_execution_design.md

## Forbidden Files

- docs/plan/agent_bridge_mvp.md
- .git/**
- .agent/runs/**
- .agent/metrics/**
- .agent/sessions/*.json

## Required Commands

- uv run agent-bridge task validate --spec .agent/tasks/commander_worktree_execution_design.toml
- uv run agent-bridge task render --spec .agent/tasks/commander_worktree_execution_design.toml --out .agent/tasks/commander_worktree_execution_design.md

## Acceptance Criteria

- Design uses git worktree as the default write-capable isolation unit.
- Design keeps active workspace untouched by default.
- Design exports a standard patch artifact from the isolated worktree.
- Design explains how result checks avoid unrelated dirty active workspace changes.
- Do not implement code changes.

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
