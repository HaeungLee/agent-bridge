# Agent Bridge MVP Plan

Date: 2026-05-21

## 1. Purpose

Agent Bridge is a CLI-first control plane that lets a commander agent delegate expensive or repetitive development work to cheaper coding agents while preserving final decision quality.

The first commander target is Codex/GPT-5.5. Later commanders may include Claude Code, OpenCode, Gemini, Moonlight, or any other CLI-capable agent.

The goal is not to find one best model. The goal is to measure which model and harness combination performs well for each class of work, then route future tasks accordingly.

Core principle:

```text
Lower-cost agents spend the work tokens.
Higher-quality commander agents spend the judgment tokens.
```
Primary MVP use case:

Codex/GPT-5.5 should be able to invoke Agent Bridge as a local CLI tool from inside its coding harness, instead of asking the user to manually open multiple agent UIs.

The bridge exposes many agents as one stable command surface:

```text
Codex -> agent-bridge -> runner/provider/model -> normalized report
```
The commander should only need to know the bridge contract, not each agent's raw CLI/API details.

## 2. Why CLI First

Most useful coding agents need workspace access. Raw model APIs are useful for report-only jobs, but they do not naturally inspect, edit, test, or navigate a repository without the commander packaging context for them.

Agent Bridge therefore starts as a CLI orchestrator:

```text
Commander agent
  -> agent-bridge CLI
    -> runner adapter
      -> OpenCode / Claude Code / Gemini CLI / Codex CLI / raw API
        -> provider and model
```

MCP is a later integration layer, not the MVP. A CLI is easier to debug, easier to call from Codex, and easier to port into Moonlight as a subprocess adapter.

## 3. Language Decision

MVP language: Python 3.12.

Reasons:

- Fast adapter development.
- Strong subprocess and filesystem ergonomics.
- Easy OpenAI-compatible API integration.
- Good JSON/YAML/config ecosystem.
- Simple packaging with `uv`.
- Better fit for prompt templates, reports, and experimental metrics than Rust at this stage.

Rust remains the long-term Moonlight control-plane language. Once contracts stabilize, Moonlight can absorb the bridge through a subprocess adapter, HTTP adapter, MCP server, or native Rust implementation.

## 4. Commander Role

The commander agent owns:

- User conversation and intent clarification.
- Work decomposition.
- Phase, milestone, and task planning.
- Agent selection.
- Delegation prompts.
- Acceptance criteria.
- Reading compact reports.
- Approving or rejecting outputs.
- Final integration and commit decision.
- Updating routing policy from observed results.

The commander should avoid reading raw subagent transcripts unless needed. Raw output can contaminate context, waste tokens, or anchor the commander on a bad implementation.

## 5. Subagent Role

Subagents own:

- Repository inspection.
- Long-context code reading.
- Boilerplate implementation.
- Test writing.
- Bug tracing.
- First-pass refactors.
- Alternative designs.
- Code review.
- Risk analysis.
- Patch generation.

Subagents may produce patches, but MVP policy is that patches are outputs, not automatically trusted changes.

Preferred default:

```text
Subagent writes patch/report.
Bridge normalizes output.
Commander reads compact report first.
Commander opens raw diff only when needed.
```

## 6. Context Contamination Policy

The bridge must not push raw model output directly into the commander context by default.

Every run should produce:

- `summary.md`: short commander-readable summary.
- `decision_report.json`: normalized structured result.
- `diffstat.txt`: changed file count and line count.
- `touched_files.json`: exact file list.
- `risks.md`: known risks and uncertainties.
- `tests.md`: commands run and results.
- `raw/`: raw transcripts, prompts, stderr, stdout.

The commander reads `summary.md` and `decision_report.json` first. Raw files are inspected only for unclear, risky, or failing cases.

## 7. Project Workflow

The user's current manual workflow is retained and formalized.

```text
Idea discussion
  -> immutable plan
  -> mutable roadmap
  -> phase plan
  -> milestones/tasks
  -> delegated agent work
  -> yyyymmdd_process.md logs
  -> commander review
  -> user checkpoint
  -> commit
  -> final E2E
```

### 7.1 Immutable Plan

The plan captures direction that should not casually change.

The plan must remain a single file even when it becomes long. Splitting the plan across multiple files weakens continuity and can cause future agents to miss core decisions.

Plan policy:

- Keep one canonical plan file.
- Do not split the plan by phase, date, or agent.
- Do not rewrite historical decisions silently.
- Add amendments or superseding decisions in-place with dates.
- Use the roadmap for execution changes instead of mutating the plan's core direction.

Required fields:

- Problem statement.
- Product or engineering goal.
- Non-goals.
- Constraints.
- Architecture decision.
- Quality bar.
- Risk model.
- Exit criteria.

Plans can be superseded by a new plan, but should not be silently rewritten.

### 7.2 Mutable Roadmap

The roadmap tracks current execution state.

Required fields:

- Current phase.
- Completed milestones.
- Active milestones.
- Pending milestones.
- Blockers.
- Changed assumptions.
- Next checkpoint.

The roadmap is allowed to change as implementation teaches us more.

### 7.3 Phase, Milestone, Task

Each phase contains milestones. Each milestone may contain tasks.

Recommended hierarchy:

```text
Phase: stable product slice
Milestone: reviewable unit suitable for user checkpoint and commit
Task: delegatable unit for one agent run
```

Tasks should include:

- Objective.
- Workspace path.
- Files or modules in scope.
- Files or modules out of scope.
- Acceptance criteria.
- Verification command.
- Expected output contract.

### 7.4 Process Log

Every subagent must generate a process log. The process log remains the human-readable project memory.

However, the commander's primary machine-readable surface is not the process log. It is the normalized JSON report generated beside each run.

Recommended separation:

```text
process.md / yyyymmdd_process.md:
  human-readable narrative, useful for the user and cross-session continuity

decision_report.json:
  commander-readable structured result, used for routing, scoring, and review

summary.md:
  compact commander-readable human summary
```

This avoids forcing the commander to parse long prose when a structured report is enough.

Required format:

```md
# YYYYMMDD Process

## Run Metadata

- Run ID:
- Agent:
- Runner:
- Provider:
- Model:
- Role:
- Task:
- Workspace:
- Start:
- End:
- Cost USD:
- Tokens In:
- Tokens Out:

## Objective

## Files Inspected

## Files Changed

## Commands Run

## Result

## Risks

## Open Questions

## Self-Evaluation

- Correctness:
- Completeness:
- Test coverage:
- Confidence:
- Known weak points:
```

### 7.5 Parallel Work Logging

Parallel agents must not freely append to the same daily process file during execution. That creates interleaved logs, merge conflicts, and noisy commander context.

Each run writes to its own isolated run directory:

```text
.agent/runs/<run_id>/process.md
.agent/runs/<run_id>/summary.md
.agent/runs/<run_id>/decision_report.json
```

The daily process file is then generated or updated as an index and narrative rollup:

```text
docs/process/20260521_process.md
```

Daily process entries should be append-only summaries of completed runs, not raw transcripts.

Recommended daily entry:

```md
## HH:MM - <run_id> - <agent> - <task>

- Status:
- Summary:
- Files changed:
- Tests:
- Risks:
- Commander verdict:
- Links:
  - Run directory:
  - Summary:
  - Decision report:
```

If multiple agents work in parallel on the same milestone, the daily process should group by milestone:

```md
## Milestone M1: OpenCode Runner

### Runs

- 10:14 `kimi_impl`: generated first patch, partial accept.
- 10:22 `glm_review`: found config validation gap.
- 10:35 `deepseek_investigate`: traced subprocess timeout issue.

### Commander Rollup

- Accepted:
- Rejected:
- Follow-up:
```

### 7.6 Process File Size Policy

Daily process files should stay small enough for weak or medium-context agents to read reliably.

This policy applies to process/log files only. It does not apply to immutable plan documents.

Policy:

- Soft limit: 800 lines.
- Hard limit: 900 lines.
- Never exceed 1000 lines intentionally.

When the active process file reaches the soft limit, create the next numbered file:

```text
20260521_process.md
20260521_process2.md
20260521_process3.md
```

The first file should include an index if the day is split:

```md
## File Index

- `20260521_process.md`: setup, M1 scaffold
- `20260521_process2.md`: M2 runner integration
- `20260521_process3.md`: review, eval, handoff
```

Bridge behavior:

- Check line count before appending.
- If current file has 800 or more lines, create the next numbered file.
- Add a short rollover note to both files.
- Keep `latest_process.md` or an equivalent pointer if useful.

This preserves the user's existing workflow while keeping logs friendly to agents that read in 800-line chunks.

## 8. MVP Commands

Initial CLI:

```powershell
agent-bridge doctor
agent-bridge run --agent glm_review --task .agent/tasks/task.md --workspace W:\Projects\ProjectML\moonlight
agent-bridge summarize --run latest
agent-bridge compare --runs runA runB
agent-bridge eval --run latest
```

Optional later commands:

```powershell
agent-bridge plan init
agent-bridge roadmap update
agent-bridge task create
agent-bridge route suggest --task .agent/tasks/task.md
agent-bridge report daily
```

## 9. Initial Directory Contract

```text
agent-bridge/
  pyproject.toml
  README.md
  AGENTS.md
  config/
    agents.yaml
    runners.yaml
    providers.yaml
  docs/
    plan.md
    roadmap.md
  src/
    agent_bridge/
      cli.py
      contracts.py
      config.py
      runs.py
      normalizer.py
      evaluator.py
      routing.py
      runners/
        base.py
        opencode.py
        claude_code.py
        gemini_cli.py
        codex_cli.py
        raw_openai.py
  .agent/
    tasks/
    runs/
    reports/
    metrics/
```

Run directory:

```text
.agent/runs/20260521-153012-glm_review/
  request.json
  summary.md
  decision_report.json
  diffstat.txt
  touched_files.json
  tests.md
  risks.md
  process.md
  metrics.json
  raw/
    prompt.md
    stdout.txt
    stderr.txt
    transcript.md
```

## 10. Agent Configuration

Example `config/agents.yaml`:

```yaml
agents:
  glm_review:
    runner: opencode
    provider: nanogpt
    model: glm-5.2
    role: code_review
    default_mode: review
    max_cost_usd: 1.0
    output_contract: review_v1

  kimi_impl:
    runner: opencode
    provider: nanogpt
    model: kimi-k2.6
    role: implementation
    default_mode: patch
    max_cost_usd: 2.0
    output_contract: patch_v1

  deepseek_investigate:
    runner: opencode
    provider: nanogpt
    model: deepseek-v4
    role: bug_investigation
    default_mode: report
    max_cost_usd: 1.5
    output_contract: investigation_v1

  grok_arch:
    runner: raw_openai
    provider: xai
    model: grok
    role: architecture_critique
    default_mode: report
    max_cost_usd: 1.5
    output_contract: critique_v1
```

## 11. Measurement and Error Tracking

The bridge should collect simple metrics from day one. Perfect automated evaluation is not required. The MVP should capture enough evidence for the commander to improve routing decisions.

### 11.1 Run Metrics

Each run records:

- Agent, runner, provider, model.
- Task type.
- Workspace.
- Files inspected.
- Files changed.
- Lines added/deleted.
- Commands run.
- Test pass/fail/unknown.
- Runtime duration.
- Estimated cost.
- Token usage if available.
- Commander verdict.
- User verdict if available.

### 11.2 Error Categories

Use a small fixed taxonomy:

```text
none
compile_error
test_failure
wrong_requirement
over_editing
under_editing
hallucinated_file
bad_api_assumption
style_mismatch
unsafe_change
poor_explanation
format_violation
timeout
tool_failure
unknown
```

### 11.3 Quality Score

MVP score:

```text
score = 100
  - compile_error * 40
  - test_failure * 30
  - wrong_requirement * 35
  - unsafe_change * 35
  - hallucinated_file * 25
  - over_editing * 20
  - under_editing * 15
  - style_mismatch * 10
  - format_violation * 10
  - poor_explanation * 5
```

The score is not a universal model benchmark. It is a local routing signal for this user's repositories and workflow.

### 11.4 Commander Verdict

After review, the commander writes:

```json
{
  "accepted": false,
  "acceptance_level": "none|partial|full",
  "error_categories": ["test_failure", "style_mismatch"],
  "score": 55,
  "best_use_case": "bug investigation",
  "avoid_for": "large autonomous refactors",
  "notes": "Good trace, weak patch quality."
}
```

### 11.5 Routing Memory

The bridge maintains `.agent/metrics/model_routing.md`.

Suggested format:

```md
# Model Routing Notes

## glm-5.2 via nanogpt/opencode

- Strong:
- Weak:
- Best task types:
- Avoid:
- Recent score average:
- Commander notes:
```

## 12. Safety Gates

MVP gates:

- No direct commits by subagents.
- No destructive commands unless explicitly allowed.
- No automatic patch apply in default mode.
- Subagent must declare files changed.
- Bridge must preserve raw logs.
- Commander reads compact report before raw transcript.
- High-risk changes require review agent or commander direct implementation.

High-risk tasks include:

- Auth.
- Billing.
- Data deletion.
- Migration.
- Security boundary.
- Large cross-module refactor.
- Public API contract.
- Deployment configuration.

## 13. Antigravity Strategy

Antigravity 2.0 is not treated as a primary human UI.

If it exposes a usable CLI or automation path, it becomes a paid runner:

```text
agent-bridge -> antigravity runner -> Gemini/Claude capabilities
```

The value is not the UI. The value is reusing already-paid capacity as a subordinate agent.

If no stable CLI exists, defer Antigravity integration and use Gemini through other CLI/API paths.

## 14. Moonlight Migration Path

Agent Bridge should mirror Moonlight concepts without depending on Moonlight initially.

Mapping:

```text
agent-bridge run       -> Moonlight agent_run
runner adapter         -> Moonlight adapter_runtime
decision_report.json   -> AdapterResponseEnvelope data
metrics.json           -> AdapterMetrics
process.md             -> agent_session_events / narrative report
```

Migration path:

1. Build standalone Python CLI.
2. Stabilize run directory and report contracts.
3. Add Moonlight subprocess adapter.
4. Add optional MCP server.
5. Move stable orchestration into Moonlight.
6. Keep experimental runners outside Moonlight until proven.

## 15. MVP Milestones

### Milestone 1: Scaffold

- Python 3.12 project with `uv`.
- CLI entrypoint.
- Config loading.
- Run directory creation.
- `doctor`, `run`, `summarize`.

### Milestone 2: First Runner

- OpenCode runner adapter.
- Raw subprocess capture.
- Prompt template.
- Report normalization.
- Process log generation.

### Milestone 3: Metrics

- `metrics.json`.
- Error taxonomy.
- Commander verdict file.
- `eval` command.
- `model_routing.md` update.

### Milestone 4: Multi-Runner

- Raw OpenAI-compatible runner.
- xAI/nanoGPT/OpenRouter provider configs.
- Claude Code or Gemini CLI runner if available.

### Milestone 5: Moonlight Compatibility

- Contract comparison with Moonlight `adapter_runtime`.
- Export format compatible with Moonlight adapter response.
- Decide whether MCP is needed.

## 16. Open Decisions

- Whether subagents may write to a temporary git worktree or must only emit patches.
- Whether each task gets a fresh workspace clone/worktree.
- Which runner becomes the default implementation runner.
- Whether commander verdicts are written manually, semi-automatically, or through a review command.
- Whether Antigravity has a callable automation surface worth integrating.

## 17. Recommended Default Policy

Use this policy at MVP start:

```text
LOW risk:
  subagent may inspect and produce patch.
  commander reviews summary and diffstat.

MID risk:
  implementation subagent + review subagent.
  commander reviews compact reports and selected diffs.

HIGH risk:
  commander designs and may implement directly.
  subagents provide critique, investigation, or review only.
```

This keeps cost down without giving low-confidence agents authority over critical code.
