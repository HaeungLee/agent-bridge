# Task: Review execution_mode and worktree patch gate design

## Metadata

- Schema: task_spec.v0
- Task ID: review-worktree-patch-gate
- Phase: Phase 5 Follow-up
- Slice: Worktree Patch Gate Review
- Owner: commander

## Objective

Perform a read-only design review of the proposed execution_mode plus patch.diff/worktree.json gate direction. Do not modify code or documents. Focus only on design gaps, failure modes, and scope validation risks for write-capable isolated git worktree execution.

Target review files are limited to:
- src/agent_bridge/task_spec.py
- src/agent_bridge/worktrees.py
- docs/worktree_execution_v0.md
- docs/task_spec_v0.md

Assess whether execution_mode, patch.diff, and worktree.json can be added safely to the task gate without weakening commander control. Report concrete design risks and recommended next implementation slices.

## Allowed Files

- docs/plan/agent_bridge_mvp.md
- AGENTS.md
- src/agent_bridge/task_spec.py
- src/agent_bridge/worktrees.py
- docs/worktree_execution_v0.md
- docs/task_spec_v0.md

## Read Scope

- docs/plan/agent_bridge_mvp.md
- AGENTS.md
- src/agent_bridge/task_spec.py
- src/agent_bridge/worktrees.py
- docs/worktree_execution_v0.md
- docs/task_spec_v0.md

## Write Scope

- .agent/runs/**

## Forbidden Files

- .git/**
- .agent/metrics/**
- .agent/sessions/*.json
- src/agent_bridge/runs.py
- src/agent_bridge/cli.py
- src/agent_bridge/adapters/**
- config/**
- docs/process/**
- docs/plan/roadmap.md

## Required Commands

- Do not run commands that modify the working tree.
- If commands are needed, use read-only inspection commands only.

## Acceptance Criteria

- The report identifies whether execution_mode should be explicit, inferred, or omitted.
- The report identifies the minimum required worktree.json fields for gate validation.
- The report identifies how patch.diff paths should be checked against write_scope and forbidden_files.
- The report identifies failure modes that artifact existence checks alone cannot catch.
- The report identifies what should remain out of scope for the next implementation slice.
- No repository files are modified by the reviewing agent.

## Hard Rules

- Do not commit.
- Do not implement the next phase.
- Do not modify any files.
- Do not edit src/agent_bridge/task_spec.py.
- Do not edit src/agent_bridge/worktrees.py.
- Do not edit docs/worktree_execution_v0.md.
- Do not edit docs/task_spec_v0.md.
- Do not inspect files outside read_scope except if AGENTS.md requires it; if that happens, report it explicitly.
- Do not self-declare Commander Verdict or PASS.

## Expected Report

- Files inspected
- Design findings
- Failure modes
- Recommended next implementation slice
- Out of scope
- Open questions

## Execution Boundary

Implement only the task described above. Do not implement future phases, adjacent features, or optional integrations.
If a required change appears to exceed the allowed files or hard rules, stop and report the blocker.
