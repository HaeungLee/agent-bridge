# Phase 5 Handoff

Date: 2026-05-22

Status: Phase 5 closed for this session. Use this document as the next-session entry point.

## Commander Intent

Agent Bridge is a CLI-first control plane for delegating implementation, review, investigation, and reporting work to cheaper or quota-rich coding agents while Codex remains the commander and final gate.

Primary operating model:

1. Human and Codex define direction.
2. Task specs narrow the work.
3. Subagents run through CLI adapters.
4. Run artifacts and gates capture behavior.
5. Codex decides what to accept.

Do not optimize too deeply for one model. Kimi, DeepSeek, Mimo, Gemini, Antigravity, Claude Code, and future adapters should all fit the same broad control plane.

## Completed Through Phase 5

- Python 3.12 project scaffold with `uv`.
- `agent-bridge doctor`.
- Run directory lifecycle under `.agent/runs/<run_id>/`.
- `completed.marker` based latest resolution.
- `decision_report.json`, `metrics.json`, `summary.md`, per-run `process.md`, raw stdout/stderr artifacts.
- `agent-bridge summarize --run latest`.
- `task_spec.v0` TOML validation and markdown rendering.
- `agent-bridge task validate`.
- `agent-bridge task render`.
- `agent-bridge task check-result` for git changed-file scope.
- `agent-bridge task check-tool-use` for raw adapter tool-use path scope.
- `agent-bridge task gate` for completed-status plus tool-use scope.
- CLI adapter runner envelope `adapter.v0.1`.
- OpenCode readonly shim.
- OpenCode session control through `.agent/sessions`.
- Repo-local OpenCode agents:
  - `agents/bridge-smoke-agent`
  - `agents/bridge-readonly-report`
- OpenCode/nanoGPT Kimi readonly smoke and report paths.
- Antigravity smoke adapter exists, but only as a connectivity experiment.
- Gemini-specific rules file `GEMINI.md`.
- Strengthened `AGENTS.md` for scope, append-only process logs, no self-verdicts, no self-scoring.
- Read-only benchmark specs:
  - `.agent/tasks/bench_readonly_config_report.toml`
  - `.agent/tasks/bench_readonly_runner_flow_report.toml`
  - `.agent/tasks/bench_readonly_gate_report.toml`

## Important Model Observations

### Gemini / Antigravity

- Very fast, useful for small tasks and documentation/rules work.
- Tends to over-implement or move beyond the requested phase if not tightly scoped.
- Caused a serious process-log overwrite incident by trusting a directory listing and using overwrite-style writing.
- Rules now explicitly require process logs to be append-only.
- Must not self-declare `Commander Verdict: PASS` or add self-scoring like `Correctness: 5/5`.
- Use Gemini with narrow task specs and post-task `check-result`.

### Kimi k2.6 through OpenCode/nanoGPT

- Useful for compact config reports.
- Not yet reliable at staying inside explicit allowed read scope for source/gate understanding tasks.
- It read the plan/roadmap files during a gate benchmark despite the allowed-file list.
- This is model/harness behavior to record, not a reason to overfit the whole control plane around Kimi.
- Use `task gate` or `check-tool-use` after every OpenCode run.

### Antigravity CLI

- `antigravity_smoke` exists and broadly follows `adapter.v0.1`.
- It uses `--dangerously-skip-permissions`, so it is smoke-only.
- It observes global Antigravity session state and should not be treated as production-safe yet.

## Critical Safety Rules

- Never overwrite files in `docs/process/`; append only.
- Do not edit `docs/plan/agent_bridge_mvp.md` unless explicitly requested.
- Do not commit unless explicitly requested.
- Do not enable write-capable adapters in the active workspace.
- Write-capable work must start in an isolated worktree or temporary workspace.
- Subagent outputs should be reviewed through artifacts, diffs, and gates before applying.
- `task gate` is the current minimum post-run safety floor.

## Known Gaps

- `task gate` checks completed status and tool-use scope, but does not yet enforce all expected artifacts.
- `check-result` uses the whole dirty worktree and can be confused by unrelated user changes.
- Tool-use checking is strongest for OpenCode-style JSONL and `tool_use_summary`; other adapters may need normalized tool-use summaries.
- Read/write scope is not separated yet in `task_spec.v0`.
- Daily process rollup and 800-line rollover are not implemented.
- `compare --runs` is not implemented.
- No isolated write-capable worktree execution yet.

## Recommended Next Session Plan

1. Verify baseline:

   ```powershell
   git status --short
   uv run agent-bridge doctor
   uv run python -m compileall src
   ```

2. Design isolated write-capable execution:

   - Create temporary worktree/workspace.
   - Run write-capable subagent only there.
   - Capture diff as an artifact.
   - Run tests/checks in isolation.
   - Let Codex decide whether to apply patch to active workspace.

3. Extend task specs:

   - Separate `read_scope` and `write_scope`.
   - Keep `allowed_files` as compatibility until migration is done.
   - Add expected artifact requirements to `task gate`.

4. Compare models on existing read-only benchmarks:

   - Kimi k2.6
   - DeepSeek v4 pro/flash if OpenCode or another CLI can call it
   - Mimo v2.5 if available
   - Gemini/Antigravity with strict docs/rules tasks

5. Record model observations objectively:

   - Strengths
   - Scope discipline
   - Empty output / encoding / tool-use issues
   - Best use cases
   - Avoid cases

## Suggested Commit Groups

If current work is uncommitted, prefer these groups:

1. `core: add task specs and run gates`
   - task_spec validation/render/check-result/check-tool-use
   - `task gate`
   - completed marker/latest behavior

2. `adapters: add OpenCode and Antigravity smoke paths`
   - CLI adapter runner
   - OpenCode readonly shim and repo-local agents
   - Antigravity smoke adapter
   - byte-based subprocess capture

3. `docs: harden agent rules and record phase 5 handoff`
   - `AGENTS.md`
   - `GEMINI.md`
   - process logs
   - `handoff_phase5.md`
   - roadmap Phase 5 closure

4. `bench: add readonly model benchmark specs`
   - benchmark task specs and rendered prompts

## First Prompt For Next Session

```text
Read handoff_phase5.md, docs/plan/roadmap.md, docs/plan/agent_bridge_mvp.md, AGENTS.md, and GEMINI.md.
Do not modify docs/plan/agent_bridge_mvp.md.
Continue from Phase 5 handoff.
First, verify git status and doctor.
Then propose the smallest isolated worktree design for write-capable adapter execution.
Do not implement until the design is reviewed.
```
