# Task: Check raw adapter tool-use paths against task scope

## Metadata

- Schema: task_spec.v0
- Task ID: phase5b-tool-use-path-checker
- Phase: Phase 5
- Slice: Raw JSONL Tool-Use Path Checker
- Owner: commander

## Objective

Add a thin gate that reads raw run artifacts, extracts OpenCode JSONL tool_use file paths, verifies they stay within task_spec.v0 allowed_files and forbidden_files before write-capable adapters are enabled, and makes adapter subprocess decoding robust on Windows.

## Allowed Files

- src/agent_bridge/adapters/antigravity_smoke.py
- src/agent_bridge/adapters/opencode_readonly.py
- src/agent_bridge/cli.py
- src/agent_bridge/task_spec.py
- .agent/tasks/phase5b_tool_use_path_checker.toml
- .agent/tasks/phase5b_tool_use_path_checker.md
- .agent/tasks/gemini_rules_hardening.toml
- .agent/tasks/gemini_rules_hardening.md
- docs/process/20260522_process.md

## Forbidden Files

- docs/plan/agent_bridge_mvp.md
- .git/**
- .agent/runs/**
- .agent/metrics/**
- .agent/sessions/*.json

## Required Commands

- uv run python -m compileall src
- uv run agent-bridge task render --spec .agent/tasks/phase5b_tool_use_path_checker.toml --out .agent/tasks/phase5b_tool_use_path_checker.md
- uv run agent-bridge task check-tool-use --spec .agent/tasks/phase5b_readonly_report_smoke.toml --run 20260522-010013-b3d2e4-opencode_kimi_report --workspace .
- uv run agent-bridge task gate --spec .agent/tasks/phase5b_readonly_report_smoke.toml --run 20260522-010013-b3d2e4-opencode_kimi_report --workspace .
- uv run agent-bridge task check-result --spec .agent/tasks/phase5b_tool_use_path_checker.toml --workspace .

## Acceptance Criteria

- The checker parses adapter raw stdout, nested OpenCode stdout_preview JSONL, and compact tool_use_summary artifacts.
- The checker reports observed tool names and statuses.
- The checker fails on write-capable tool use.
- The checker fails on forbidden, out-of-scope, or outside-workspace file paths.
- The standard post-run task gate checks completed status and tool-use scope.
- OpenCode and Antigravity adapter shims capture child CLI stdout/stderr as bytes and decode explicitly as UTF-8 with replacement.
- The latest tightened OpenCode report run passes the tool-use path checker.

## Hard Rules

- Do not commit.
- Do not implement the next phase.
- Do not enable write-capable OpenCode execution.
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
