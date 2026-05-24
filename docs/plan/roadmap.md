# Agent Bridge Roadmap

Date: 2026-05-24

Status: current execution roadmap.

Canonical plan: `docs/plan/agent_bridge_mvp.md`.

This file is the current commander entry point for implementation state. Older plans and completed drafts may live under `docs/legacy/`.

## Current Goal

Build a Python CLI control plane that lets Codex act as commander while lower-cost or already-paid agents perform token-heavy work in controlled scopes.

Primary workflow:

```text
Codex commander
  -> task_spec.v0
  -> agent-bridge run
  -> subordinate CLI/API harness
  -> normalized run artifacts
  -> task gate
  -> commander review
```

## Active Policy

- The canonical product direction stays in `docs/plan/agent_bridge_mvp.md`.
- The active roadmap stays short and current.
- Contract docs live at `docs/task_spec_v0.md` and `docs/worktree_execution_v0.md`.
- Process logs live under `docs/process/` and are append-only.
- Sensitive local integration notes live under `docs/secret/` and must remain untracked.
- Completed or superseded planning drafts may move to `docs/legacy/`.
- Subagents must not edit the commander's active workspace by default.
- Write-capable subagents must run in isolated worktrees and export patches for review.
- Patches are never auto-applied.

## Completed Foundation

### Phase 0-3: CLI and Run Contract

- [x] Python 3.12 project and `uv` workflow.
- [x] `agent-bridge doctor`.
- [x] Config loading from TOML.
- [x] Run directory creation under `.agent/runs/<run_id>/`.
- [x] `decision_report.json`, `summary.md`, `process.md`, `metrics.json`, raw stdout/stderr.
- [x] `agent-bridge summarize`.
- [x] Local `mock_subprocess` runner for safe lifecycle verification.
- [x] `cli_adapter` runner contract for subprocess adapters.

### Phase 4: Evaluation and Routing

- [x] Error taxonomy.
- [x] Basic quality score.
- [x] `agent-bridge eval`.
- [x] Commander verdict file.
- [x] Generated routing memory under `.agent/metrics/`.

Current decision:

```text
.agent/metrics/model_routing.md is generated routing memory.
docs/model_observations.md is the human-curated commander memory.
```

### Phase 5-A: Task Specs and Gates

- [x] `task_spec.v0` TOML loading and validation.
- [x] Deterministic task rendering to Markdown.
- [x] `read_scope` and `write_scope`.
- [x] Expected artifact checks.
- [x] Tool-use path extraction from normalized adapter artifacts.
- [x] `agent-bridge task gate`.
- [x] `execution_mode = "report"` and `execution_mode = "worktree_patch"`.
- [x] `patch.diff` plus `worktree.json` gate checks.

### Phase 5-B: Agent Harnesses

- [x] OpenCode/Kimi readonly and report adapters.
- [x] OpenCode compact `final_report` artifact handling.
- [x] OpenCode DeepSeek v4 Flash Free fallback smoke.
- [x] Antigravity CLI smoke.
- [x] Antigravity XML response path with `response.xml` and parsed report support.
- [x] Claude Code via local Anthropic-to-nanoGPT proxy smoke.

Harness status:

```text
OpenCode/Kimi: useful but nanoGPT instability observed.
OpenCode DeepSeek Flash Free: useful fallback, may emit mojibake.
Antigravity XML: useful as artifact/report runner; stdout is not reliable.
Claude Code proxy: promising route for nanoGPT models missing from OpenCode registry.
```

### Phase 5-C/D/E: Worktree Patch Foundation

- [x] `src/agent_bridge/worktrees.py`.
- [x] Isolated git worktree create/remove helpers.
- [x] Base ref and base SHA metadata.
- [x] `git diff --binary` patch export including untracked files by staging inside the isolated worktree.
- [x] Task gate validation for `patch.diff` and `worktree.json`.
- [x] `agent-bridge run` orchestration for `execution_mode = "worktree_patch"`.
- [x] Runner receives the isolated worktree path, not the active workspace.
- [x] Run exports `patch.diff` and `worktree.json`.
- [x] Worktree cleanup by default, with `AGENT_BRIDGE_KEEP_WORKTREE=1` for debugging.
- [x] Mock-run verification that gate passes and cleanup occurs.

## Phase 5 Closure Checklist

Phase 5 is not closed until the following are done or explicitly deferred.

### Must Finish

- [x] Harden worktree orchestration failure artifacts.
  - Ensure config/load/provision/export failures still produce useful run artifacts when feasible.
  - Preserve cleanup guarantees.
- [ ] Harden Claude proxy adapter before write-capable use.
  - Rename confusing `opencode_deepseek_flash` agent ID to a Claude/proxy-specific ID.
  - Use `shell=False`.
  - Make base URL, port, and model mapping config-driven.
  - Allow bypass permissions only when the execution workspace is an isolated worktree.
- [ ] Add `agent-bridge compare --runs runA runB`.
  - Compare status, model, runner, runtime, cost, touched files, final report availability, risks, and verdict.
- [ ] Clarify generated routing memory.
  - Keep `.agent/metrics/model_routing.md` generated and ignored.
  - Keep `docs/model_observations.md` curated and tracked.

### Should Finish

- [ ] Add daily process rollup generator.
- [ ] Add process file line-count rollover near 800 lines.
- [ ] Add milestone grouping to process rollups.
- [ ] Add compact benchmark matrix task for:
  - OpenCode Kimi
  - OpenCode DeepSeek Flash Free
  - Antigravity XML
  - Claude proxy DeepSeek v4 Flash
  - Claude proxy DeepSeek v4 Pro
  - Claude proxy Mimo v2.5 Pro if callable

### Explicit Deferrals

- [ ] Automatic patch apply.
- [ ] Long-lived worktree pooling.
- [ ] MCP server.
- [ ] Moonlight native integration.
- [ ] Raw custom OpenAI-compatible file-editing agent.

## Recommended Next Slices

1. **Worktree Failure Hardening**
   - Commander-owned design and implementation.
   - Small, core behavior. Keep direct.

2. **Claude Proxy Hardening**
   - Commander designs exact adapter contract.
   - Implementation may be delegated after task packet is written.

3. **Compare Command**
   - Good subordinate-agent implementation task.
   - Read existing `runs.py`, `cli.py`, `metrics.json`, and reports.
   - Commander reviews output formatting and edge cases.

4. **Process Rollup and Rollover**
   - Good subordinate-agent implementation task.
   - Keep append-only and conservative.

5. **Benchmark Matrix**
   - Commander writes task specs.
   - Subagents execute comparable read-only and worktree dry-run tasks.
   - Commander updates `docs/model_observations.md`.

## Phase 6: Moonlight Compatibility

Objective: keep standalone Agent Bridge easy to absorb into Moonlight later.

Pending:

- [ ] Compare bridge run artifacts to Moonlight adapter envelope.
- [ ] Add Moonlight-compatible export shape if needed.
- [ ] Document subprocess adapter path.
- [ ] Decide whether MCP is useful after CLI workflows stabilize.

Phase 6 should wait until Phase 5 closure items no longer move the run artifact contract heavily.
