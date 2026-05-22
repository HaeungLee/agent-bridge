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
  -> agent-bridge task check-result --spec <spec.toml> --workspace <path>
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

# Optional. If omitted, allowed_files is used for read checks.
read_scope = [
  "docs/plan/agent_bridge_mvp.md",
  "docs/plan/roadmap.md",
  "src/agent_bridge/task_spec.py",
  "src/agent_bridge/cli.py",
]

# Optional. If omitted, allowed_files is used for write/result checks.
write_scope = [
  "src/agent_bridge/task_spec.py",
  "src/agent_bridge/cli.py",
]

forbidden_files = [
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
- Optional `read_scope` and `write_scope` must be non-empty lists of relative file patterns when present.
- `read_scope` and `write_scope` must not overlap `forbidden_files`.
- `forbidden_files` should include at least:
  - `.git/**`
- `hard_rules` should include at least:
  - `Do not commit.`
  - `Do not implement the next phase.`

## 5. Result Check

`task_spec.v0` includes a thin result gate:

```text
agent-bridge task check-result --spec <spec.toml> --workspace <path>
```

The checker reads `git status --porcelain=v1 --untracked-files=all` from the workspace and verifies:

- every changed file matches at least one `write_scope` pattern, or `allowed_files` if `write_scope` is absent
- no changed file matches a `forbidden_files` pattern
- untracked files are included
- renamed files are checked by their destination path

The result checker is intentionally simple. It does not parse patches, inspect line-level edits, or apply policy to ignored generated output.

## 6. Rendered Prompt

The rendered Markdown prompt should be deterministic and boring. It is an execution contract, not a motivational document.

Required sections:

```text
# Task: <title>

## Metadata
## Objective
## Allowed Files
## Read Scope
## Write Scope
## Forbidden Files
## Required Commands
## Acceptance Criteria
## Hard Rules
## Expected Report
```

`Read Scope` and `Write Scope` are rendered only when the spec defines them. `Allowed Files` remains the compatibility field for older specs and for agents that do not understand the split yet.

The rendered prompt must repeat that the agent should only implement the task described in the spec and must not implement future phases.

## 7. Non-Goals

Do not implement these in v0:

- YAML parsing
- JSON canonicalizer
- schema libraries
- automatic patch application
- real external model invocation
- worktree isolation
- line-level diff validation
- process rollover generation

## 8. Next Step

Implement:

```text
agent-bridge task validate --spec <spec.toml>
agent-bridge task render --spec <spec.toml> --out <task.md>
agent-bridge task check-result --spec <spec.toml> --workspace .
```

Then run the rendered prompt through `cli_smoke` only.
