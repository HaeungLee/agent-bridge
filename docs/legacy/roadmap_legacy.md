# Agent Bridge Roadmap

Date: 2026-05-21

Status: mutable execution document.

Canonical plan: `docs/plan/agent_bridge_mvp.md`.

This roadmap may change as implementation teaches us more. The plan remains the stable source of direction.

## Operating Rules

- Keep `docs/plan/agent_bridge_mvp.md` as one canonical plan file.
- Use this roadmap for phase state, milestone progress, and changed execution assumptions.
- Use `docs/process/YYYYMMDD_process.md` for human-readable work logs.
- Split process logs at 800 lines, but do not split the plan.
- Every delegated agent run must produce a run directory with `summary.md`, `decision_report.json`, `process.md`, and raw logs.
- Commander reads compact reports first, then opens raw logs only when needed.
- Subagents must not edit the active workspace directly by default.
- Subagent implementation results should be exported as patches from isolated temp workspaces/worktrees.

## Current Goal

Build a Python 3.12 CLI bridge that lets Codex or another commander agent delegate implementation, review, investigation, and critique work to cheaper CLI-capable coding agents.

Initial experiment target:

```text
Commander: Codex/GPT-5.5
Subagent candidate: Antigravity 2.0 / Gemini 3.5
Primary output: structured run report + human process log
```

## Phase 0: Setup and Ground Rules

Objective: make the project easy for any agent to enter without losing the intended direction.

Milestones:

- [x] Create canonical MVP plan.
- [x] Define plan/roadmap/process separation.
- [x] Define process rollover policy.
- [x] Create project scaffold.
- [x] Create initial `AGENTS.md`.
- [x] Create process directory and first process log.

Acceptance criteria:

- A new agent can read `docs/plan/agent_bridge_mvp.md` and `docs/plan/roadmap.md` and understand the task.
- The plan is treated as immutable direction.
- The roadmap is treated as mutable execution state.

## Phase 1: Python CLI Scaffold

Objective: create a minimal runnable CLI with stable directories and config loading.

Milestones:

- [x] Initialize Python 3.12 project with `uv`.
- [x] Add CLI entrypoint.
- [x] Add `agent-bridge doctor`.
- [x] Add config loading for agents/runners/providers.
- [x] Add run ID generation.
- [x] Add run directory creation.
- [x] Add structured error handling.
- [x] Add minimal `decision_report.v0` contract skeleton.

Suggested files:

```text
pyproject.toml
src/agent_bridge/cli.py
src/agent_bridge/config.py
src/agent_bridge/contracts.py
src/agent_bridge/runs.py
config/agents.toml
config/runners.toml
config/providers.toml
```

Acceptance criteria:

- `agent-bridge doctor` runs locally.
- A run directory can be created without calling any external model.
- Missing config produces readable errors.

## Phase 2: Run Contract and Reports

Objective: make every agent run produce commander-readable and human-readable artifacts.

Milestones:

- [x] Define `decision_report.json` schema.
- [x] Define `metrics.json` schema.
- [x] Generate `summary.md`.
- [x] Generate per-run `process.md`.
- [x] Capture raw stdout/stderr/transcript under `raw/`.
- [x] Add `agent-bridge summarize --run latest`.

Acceptance criteria:

- Commander can inspect `summary.md` and `decision_report.json` without reading raw logs.
- Human process logs remain readable.
- Raw output is preserved but isolated.

## Phase 3: First Runner Adapter

Objective: verify the bridge contract with a stable local runner before integrating unstable external tools.

Preferred experiment:

```text
1. Implement `mock_subprocess` runner first.
2. Use it to verify run directory creation, report normalization, raw log capture, summary generation, and error handling.
3. Investigate Antigravity/Gemini callable surface after the local contract works.
```

Milestones:

- [x] Implement runner adapter interface.
- [x] Implement `mock_subprocess` runner.
- [x] Pass task prompt and workspace path.
- [x] Capture output.
- [x] Normalize output into reports.
- [x] Investigate callable Antigravity/Gemini surface (Explicitly deferred to Moonlight integration).

Acceptance criteria:

- `agent-bridge run --agent <agent> --task <task> --workspace <path>` completes.
- The run creates all required artifacts.
- Failures are represented as structured reports, not just crashes.

## Phase 4: Evaluation and Routing Memory

> [!NOTE]
> Phase 4 was implemented early due to scope drift, then accepted after review.

Objective: begin measuring model usefulness and error patterns.

Milestones:

- [x] Implement error taxonomy.
- [x] Implement basic quality score.
- [x] Add `agent-bridge eval --run latest`.
- [x] Add commander verdict file.
- [x] Create `.agent/metrics/model_routing.md`.
- [x] Update routing notes from run results.

Acceptance criteria:

- Each run can be marked accepted, partially accepted, or rejected.
- Error categories are recorded.
- The project starts accumulating model-specific routing evidence.

## Phase 5: Multi-Agent Workflow

Objective: support multiple agents without corrupting logs or commander context.

Before Phase 5 implementation, complete these cleanup gates:

- [x] Stabilize `latest` resolution so it ignores in-progress or incomplete run directories.
- [ ] Decide whether `.agent/metrics/model_routing.md` is tracked source, generated output, or replaced by a sample file.
- [x] Keep `mynote` valid UTF-8/ASCII and aligned with `AGENTS.md`.
- [x] Strengthen `AGENTS.md` scope-control rules before delegating more Antigravity work.

Milestones:

- [x] Ensure each run writes only to its own run directory.
- [x] Define `task_spec.v0` authoring and canonicalization flow.
- [x] Add `agent-bridge task validate` for canonical task specs.
- [x] Add preflight checks for allowed files, forbidden files, constraints, and verification commands.
- [x] Add result checks for forbidden file changes and raw tool-use path violations.
- [ ] Add daily process rollup generator.
- [ ] Add process file line-count rollover at 800 lines.
- [ ] Add `agent-bridge compare --runs runA runB`.
- [ ] Add milestone grouping in process rollups.

Acceptance criteria:

- Parallel runs do not interleave raw logs.
- Delegation prompts can be generated from validated task specs instead of long ad hoc natural-language prompts.
- LLM-authored specs are canonicalized into strict JSON before execution.
- Daily process remains readable.
- Commander can compare outputs without reading all transcripts.

Phase 5 closure note:

- `task_spec.v0` validation/render/check-result is implemented.
- `agent-bridge task check-tool-use` and `agent-bridge task gate` are implemented as the pre-write-capable safety floor.
- OpenCode/nanoGPT readonly smoke, session reuse, repo-local pure agents, readonly report agent, and benchmark specs are implemented.
- Antigravity CLI smoke exists but remains smoke-only because it uses `--dangerously-skip-permissions` and global session-state observation.
- Write-capable execution is explicitly deferred to the next phase/session and should start with isolated worktrees.

## Phase 6: Moonlight Compatibility

Objective: keep the standalone bridge easy to migrate into Moonlight.

Milestones:

- [ ] Compare bridge report contract with Moonlight adapter envelope.
- [ ] Add Moonlight-compatible export shape.
- [ ] Document subprocess adapter path.
- [ ] Decide whether MCP is needed after CLI proves useful.

Acceptance criteria:

- Bridge output can be mapped to Moonlight `adapter_runtime`.
- Moonlight migration path is documented.

## Delegation Packet for Gemini

Use this section when handing implementation to Gemini or another subagent.

Task:

```text
Read `docs/plan/agent_bridge_mvp.md` and `docs/plan/roadmap.md`.
Implement only the remaining Phase 0 setup work and the smallest useful CLI skeleton.
Do not change the canonical plan unless explicitly asked.
Update the roadmap checkboxes for completed Phase 0 items only.
Create or update a human-readable process log.
Produce a compact summary of changed files, commands run, risks, and open questions.
```

Hard rules:

- Do not split `docs/plan/agent_bridge_mvp.md`.
- Do not let raw transcripts replace structured reports.
- Do not write unrelated features.
- Do not commit.
- Prefer small, reviewable changes.
- Do not integrate real external models yet.
- Do not implement Antigravity yet.
- Do not implement OpenCode yet.
- Do not call APIs.
- Do not add complex abstractions.
- Use TOML config with standard-library `tomllib`, not YAML.
- Use standard-library `argparse`, not Click or Typer.
- Do not add new runtime dependencies for the scaffold.

Expected report:

```text
Changed files:
Commands run:
Result:
Risks:
Open questions:
Next recommended step:
```

## Current Next Step

Phase 5 is closed for the current session. Start the next session from `handoff_phase5.md`.

Recommended next work: design isolated worktree execution for write-capable adapters, then compare Kimi/DeepSeek/Mimo on the existing benchmark task specs.
