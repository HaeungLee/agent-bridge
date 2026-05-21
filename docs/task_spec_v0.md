# Task Spec v0

Date: 2026-05-21

Status: Phase 5-A foundation contract.

Purpose: define a small, validated task contract that can be rendered into an agent prompt before `agent-bridge run` delegates work to any subagent.

## 1. Design Goal

`task_spec.v0` is a scope governor.

It should prevent long natural-language delegation prompts from becoming ambiguous, over-broad, or phase-jumping. The commander can write or generate a spec, validate it, render it into a Markdown task prompt, and then pass that rendered prompt to an agent runner.

Flow:

```text
discussion
  -> task_spec.v0 TOML
  -> agent-bridge task validate --spec <spec.toml>
  -> agent-bridge task render --spec <spec.toml> --out <task.md>
  -> agent-bridge run --agent <agent> --task <task.md> --workspace <path>
```

`agent-bridge run` keeps accepting Markdown task files. This preserves the current run lifecycle and makes the task contract an explicit preflight layer.

## 2. Format

Use TOML for v0.

Reasons:

- Python 3.12 has standard-library `tomllib` for parsing.
- The project already uses TOML config.
- TOML is friendlier for human-edited multiline prompts than strict JSON.
- Later, a canonical JSON form can be generated after validation.

## 3. Required Fields

```toml
schema_version = "task_spec.v0"
task_id = "phase5a-task-spec-validation"
phase = "Phase 5"
slice = "Task Spec Validation"
title = "Implement task_spec.v0 validation"
owner = "commander"

objective = """
Add validation and rendering for structured task specs.
"""

allowed_files = [
  "src/agent_bridge/task_spec.py",
  "src/agent_bridge/cli.py",
]

forbidden_files = [
  "agent_bridge_mvp.md",
  ".git/**",
  ".agent/runs/**",
]

required_commands = [
  "uv run agent-bridge doctor",
  "uv run agent-bridge task validate --spec .agent/tasks/sample_task_spec.toml",
]

acceptance_criteria = [
  "Valid specs exit 0.",
  "Invalid specs exit 1.",
]

hard_rules = [
  "Do not commit.",
  "Do not implement the next phase.",
]

expected_report_sections = [
  "Changed files",
  "Commands run",
  "Result",
  "Risks",
  "Open questions",
  "Next recommended step",
]
```

## 4. Validation Rules

MVP validation is static.

Required checks:

- `schema_version` must equal `task_spec.v0`.
- Required string fields must be non-empty strings.
- Required list fields must be non-empty lists of non-empty strings.
- File pattern fields must not contain absolute paths.
- File pattern fields must not contain parent traversal (`..`).
- `allowed_files` and `forbidden_files` must not contain the same normalized pattern.
- `forbidden_files` should include at least:
  - `agent_bridge_mvp.md`
  - `.git/**`
- `hard_rules` should include at least:
  - `Do not commit.`
  - `Do not implement the next phase.`

v0 does not inspect the final git diff. Result checking is a later phase.

## 5. Rendered Prompt

The rendered Markdown prompt should be deterministic and boring. It is an execution contract, not a motivational document.

Required sections:

```text
# Task: <title>

## Metadata
## Objective
## Allowed Files
## Forbidden Files
## Required Commands
## Acceptance Criteria
## Hard Rules
## Expected Report
```

The rendered prompt must repeat that the agent should only implement the task described in the spec and must not implement future phases.

## 6. Non-Goals

Do not implement these in v0:

- YAML parsing
- JSON canonicalizer
- schema libraries
- automatic patch application
- real external model invocation
- worktree isolation
- result diff validation
- process rollover generation

## 7. Next Step

Implement:

```text
agent-bridge task validate --spec <spec.toml>
agent-bridge task render --spec <spec.toml> --out <task.md>
```

Then run the rendered prompt through `cli_smoke` only.
