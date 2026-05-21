# Task: Implement task_spec.v0 validation and rendering

## Metadata

- Schema: task_spec.v0
- Task ID: phase5a-task-spec-validation
- Phase: Phase 5
- Slice: Task Spec Validation
- Owner: commander

## Objective

Add a narrow task_spec.v0 preflight layer. The bridge should validate a TOML task spec and render it into a deterministic Markdown task prompt that can be passed to the existing run lifecycle.

## Allowed Files

- docs/task_spec_v0.md
- src/agent_bridge/task_spec.py
- src/agent_bridge/cli.py
- .agent/tasks/phase5a_task_spec_validation.toml
- .agent/tasks/phase5a_task_spec_validation.md
- docs/process/20260521_process.md
- roadmap.md

## Forbidden Files

- agent_bridge_mvp.md
- .git/**
- .agent/runs/**
- src/agent_bridge/runners/cli_adapter.py
- src/agent_bridge/runners/mock_subprocess.py

## Required Commands

- uv run agent-bridge task validate --spec .agent/tasks/phase5a_task_spec_validation.toml
- uv run agent-bridge task render --spec .agent/tasks/phase5a_task_spec_validation.toml --out .agent/tasks/phase5a_task_spec_validation.md
- uv run agent-bridge run --agent cli_smoke --task .agent/tasks/phase5a_task_spec_validation.md --workspace .
- uv run agent-bridge doctor

## Acceptance Criteria

- Valid task_spec.v0 TOML exits 0.
- Rendered Markdown prompt is deterministic and includes all required sections.
- The existing run command accepts the rendered Markdown task.
- No OpenCode, nanoGPT, external API, worktree, or patch workflow is implemented.

## Hard Rules

- Do not commit.
- Do not implement the next phase.
- Do not integrate OpenCode.
- Do not call external APIs.
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
