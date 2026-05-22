# Task: Harden agent operating rules for Gemini and Antigravity

## Metadata

- Schema: task_spec.v0
- Task ID: gemini-rules-hardening
- Phase: Phase 5
- Slice: Agent Rules Hardening
- Owner: commander

## Objective

Tighten repository operating rules so Gemini/Antigravity subagents stay inside assigned phases, avoid self-declared commander verdicts, and stop after updating process logs. This task is rules/documentation only.

## Allowed Files

- AGENTS.md
- GEMINI.md
- .agent/tasks/gemini_rules_hardening.toml
- .agent/tasks/gemini_rules_hardening.md
- docs/process/20260522_process.md

## Forbidden Files

- agent_bridge_mvp.md
- roadmap.md
- src/**
- config/**
- .git/**
- .agent/runs/**
- .agent/metrics/**
- .agent/sessions/*.json

## Required Commands

- uv run agent-bridge task validate --spec .agent/tasks/gemini_rules_hardening.toml
- uv run agent-bridge task render --spec .agent/tasks/gemini_rules_hardening.toml --out .agent/tasks/gemini_rules_hardening.md
- uv run agent-bridge task check-result --spec .agent/tasks/gemini_rules_hardening.toml --workspace .

## Acceptance Criteria

- Rules explicitly forbid implementing next phases or adjacent features.
- Rules explicitly forbid self-declaring Commander Verdict or PASS.
- Rules require agents to stop after the requested unit and process-log update.
- Rules tell agents to report blockers instead of widening scope.
- No source code or config files are modified.

## Hard Rules

- Do not commit.
- Do not implement the next phase.
- Do not modify source code.
- Do not modify config files.
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
