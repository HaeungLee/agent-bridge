# Task: Implement isolated git worktree helper module

## Metadata

- Schema: task_spec.v0
- Task ID: phase5c-worktree-helpers
- Phase: Phase 5 Follow-up
- Slice: Isolated Worktree Helpers
- Owner: commander

## Objective

Implement the first isolated git worktree foundation for future write-capable subordinate execution. Add a small helper module that can create a detached temporary worktree from HEAD, record base metadata, export a binary patch including untracked files if practical, list changed files, and remove the worktree. Do not integrate this into agent-bridge run yet.

## Allowed Files

- docs/worktree_execution_v0.md
- src/agent_bridge/worktrees.py
- .agent/tasks/phase5c_worktree_helpers.toml
- .agent/tasks/phase5c_worktree_helpers.md
- docs/process/20260522_process.md

## Read Scope

- docs/plan/agent_bridge_mvp.md
- docs/plan/roadmap.md
- AGENTS.md
- docs/worktree_execution_v0.md
- src/agent_bridge/worktrees.py
- .agent/tasks/phase5c_worktree_helpers.toml
- .agent/tasks/phase5c_worktree_helpers.md

## Write Scope

- src/agent_bridge/worktrees.py
- .agent/tasks/phase5c_worktree_helpers.md
- docs/process/20260522_process.md

## Forbidden Files

- .git/**
- .agent/runs/**
- .agent/metrics/**
- .agent/sessions/*.json
- src/agent_bridge/runs.py
- src/agent_bridge/cli.py
- src/agent_bridge/task_spec.py

## Required Commands

- uv run agent-bridge task validate --spec .agent/tasks/phase5c_worktree_helpers.toml
- uv run agent-bridge task render --spec .agent/tasks/phase5c_worktree_helpers.toml --out .agent/tasks/phase5c_worktree_helpers.md
- uv run python -m compileall src
- uv run agent-bridge doctor

## Acceptance Criteria

- A new src/agent_bridge/worktrees.py module exists.
- The module uses subprocess.run with shell=False for git commands.
- The module can resolve git root and HEAD SHA.
- The module can create a detached temporary worktree outside the active repository tree.
- The module can write worktree metadata with run_id, repo_root, worktree_path, base_ref, base_sha, and branch_name.
- The module can export a binary patch from the isolated worktree.
- The module can remove the isolated worktree.
- No active workspace source files are modified except allowed files.
- Do not wire the helper into agent-bridge run yet.

## Hard Rules

- Do not commit.
- Do not implement the next phase.
- Do not modify docs/plan/agent_bridge_mvp.md.
- Do not modify docs/plan/roadmap.md.
- Do not change agent-bridge run behavior.
- Do not add runtime dependencies.
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
