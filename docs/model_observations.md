# Model Observations

Date: 2026-05-24

Purpose: record commander-curated observations from actual Agent Bridge work. This is not a universal model ranking.

Generated routing memory belongs under `.agent/metrics/` and is intentionally ignored by Git. This file is the tracked human-readable routing memory.

## Routing Memory Boundary

- `.agent/metrics/model_routing.md` is generated from completed run evaluations.
- `.agent/metrics/model_routing.md` must not be edited by hand.
- `.agent/metrics/model_routing.md` must not be treated as reliable historical evidence when it conflicts with process logs or commander review.
- `docs/benchmarks/model_benchmarks.jsonl` is tracked commander-curated benchmark evidence.
- `docs/model_observations.md` is the curated source for commander routing decisions.
- Process logs under `docs/process/` remain the human audit trail for what actually happened.

## Operating Principle

Use expensive frontier models for judgment:

- architecture decisions
- task decomposition
- safety gates
- final acceptance
- cross-agent review
- fixing failed subordinate-agent work

Use cheaper or already-paid agents for work-token-heavy tasks:

- repository inspection
- narrow implementation
- first-pass reports
- smoke validation
- benchmark runs
- repetitive documentation or artifact generation

## Current Commander

### Codex / GPT-5.5

- Observed role: commander, architect, reviewer, quality gate.
- Strengths observed: preserving project direction, finding scope drift, designing safety gates, reviewing unreliable agent outputs, turning scattered logs into executable next steps.
- Risks observed: high quota cost; can spend too many tokens doing implementation directly.
- Recommended use: core design, worktree/write-safety foundation, review of subordinate patches, final acceptance, failed-run recovery.
- Avoid: long repetitive repository reading when a subordinate agent can produce a compact report.

## Harness Observations

### OpenCode / Kimi K2.6 via nanoGPT

- Observed role: initial implementation and report candidate.
- Strengths observed: can perform narrow implementation and repository analysis when nanoGPT responds normally.
- Failures observed: repeated empty responses from nanoGPT API; frequent compaction behavior; reliability concerns during the observed period.
- Benchmark observation: active-workspace read-only config benchmark completed with normalized artifacts; measured `runtime_seconds` was 23.04s for `20260524-174722-b9c3e2-opencode_kimi_report`.
- Recommended use: implementation candidate only after task specs are strict and retries are cheap.
- Guardrail: require small `allowed_files`, `write_scope`, expected artifacts, and post-run patch gate.

### OpenCode / DeepSeek v4 Flash Free

- Observed role: fallback read-only reporter through OpenCode's free quota.
- Strengths observed: callable through OpenCode when newer nanoGPT model IDs are blocked by OpenCode registry; useful for low-cost fallback review.
- Failures observed: report text may contain mojibake; long tool streams can bury final answers unless compact final-report extraction is used.
- Benchmark observation: active-workspace read-only config benchmark completed with normalized artifacts; measured `runtime_seconds` was 27.43s for `20260524-174751-d7dc59-opencode_deepseek_flash_free`.
- Recommended use: fallback read-only analysis, quick second opinion, benchmark comparison.
- Guardrail: prefer compact report mode and evaluate artifact quality separately from reasoning quality.

### Antigravity / Gemini

- Observed role: already-paid implementation/review capacity through Antigravity CLI.
- Strengths observed: fast implementation, useful when task is narrow, can produce XML artifact reports after adapter hardening.
- Failures observed: stdout is not a reliable communication surface on Windows; scratch-file mtime detection was brittle; Windows CP949/UTF-8 mismatch caused decode failures; stdin handling can hang if not controlled.
- Current status: usable as XML/report artifact runner, not as a trusted stdout runner.
- Benchmark observation: active-workspace read-only config benchmark completed with normalized artifacts; measured `runtime_seconds` was 79.51s for `20260524-174826-de362f-antigravity_xml`. The run reported one touched file, `.agent/tasks/bench_readonly_config_report.md`, so task-file mutation should be checked in future Antigravity read-only benchmarks.
- Recommended use: narrow report or implementation tasks after XML/report contract is enforced.
- Guardrail: use explicit output artifact contracts; do not rely on stdout; keep hard stop instructions.

### Claude Code / local Anthropic-to-nanoGPT proxy

- Observed role: alternative harness for nanoGPT models missing from OpenCode's registry.
- Strengths observed: read-only smoke succeeded through Claude Code harness and local proxy; promising path for DeepSeek v4 Pro/Flash and Mimo v2.5 Pro.
- Failures observed: proxy is outside the repository; Windows launcher resolution required explicit handling after moving away from `shell=True`; output can still contain mojibake.
- Current status: read-only smoke passed through `claude_deepseek_flash_proxy`; adapter now uses `shell=False`, config-driven proxy/model values, and blocks permission bypass unless the workspace is an Agent Bridge isolated worktree.
- Benchmark observation: active-workspace read-only config benchmark completed with normalized artifacts; measured `runtime_seconds` was 208.21s for `20260524-174955-fa2786-claude_deepseek_flash_proxy`, making it unsuitable for routine low-complexity read-only analysis.
- Recommended use: benchmark candidate and future implementation harness after worktree-only safety checks.
- Guardrail: keep the `claude_*_proxy` naming convention; require isolated worktree before bypass permissions; keep proxy path and secrets out of tracked source.

## Model Availability Notes

Direct nanoGPT API smoke reported callable:

- `deepseek/deepseek-v4-pro`
- `nano-gpt/deepseek/deepseek-v4-pro`
- `deepseek/deepseek-v4-flash`
- `nano-gpt/deepseek/deepseek-v4-flash`
- `xiaomi/mimo-v2.5-pro`

OpenCode registry limitation:

- Latest DeepSeek v4 and Mimo v2.5 model IDs were not available through OpenCode during testing.
- `opencode/deepseek-v4-flash-free` is available as a useful fallback quota.

Claude proxy hypothesis:

- Claude Code plus local proxy may bypass OpenCode registry lag and access newer nanoGPT models.
- Needs smoke matrix before routing decisions.

## Current Routing Plan

### Current Task-Class Candidates

Based on commander-curated benchmark evidence in `docs/benchmarks/model_benchmarks.jsonl`:

- `readonly_report`
  - Primary candidate: `opencode_kimi_report`.
  - Fallback/observation: `opencode_deepseek_flash_free`.
  - Special quota path: `antigravity_xml`, but only with strict read-only mutation checks.
- `worktree_patch`
  - Primary candidate for new-file/simple fixture creation: `aider_deepseek_flash`.
  - Primary candidate for existing-function edits and small test additions: `opencode_kimi_impl`.
  - Secondary candidate for fresh isolated new-file tasks: `aider_mimo_pro`.
  - Observation candidate: `aider_deepseek_pro`, correct but not clearly better than Flash on the current small benchmark.
  - Secondary fallback: `aider_glm51`, correct but slower and more verbose in the current small benchmark.
  - Avoid for now: Aider direct routes for existing-file edits until the adapter passes explicit files to Aider or otherwise forces real edits; both DeepSeek Flash and Mimo returned report/code text without modifying `src/agent_bridge/benchmarks.py` in the existing-function edit sample.
- `worktree_patch_test_addition`
  - Current candidate: `opencode_kimi_impl`; its patch passed isolated pytest verification.
  - Avoid for now: `aider_mimo_pro` for this task class because the sample produced no patch.
  - Caution: `aider_deepseek_flash` produced a patch and passed the current gate, but isolated pytest failed on Windows path semantics.
- `worktree_patch_continue`
  - Current candidate: `aider_deepseek_flash`.
  - Avoid for now: restored-history `aider_mimo_pro`, because the pilot returned code in the report without modifying the isolated worktree.
- `deep_review_or_investigation`
  - Observation candidate: `claude_deepseek_flash_proxy`, but current proxy overhead makes it unsuitable for routine tasks.

### Commander-Owned

- Worktree orchestration and failure hardening.
- Claude proxy safety contract.
- Task packet design for benchmark matrix.
- Final code review and acceptance.

### Good Delegation Candidates

- `agent-bridge compare` implementation.
- Process rollup and rollover utilities.
- Benchmark execution across configured harnesses.
- First-pass review of narrow patches.

### Avoid Delegating for Now

- Canonical plan rewrites.
- Worktree safety policy changes.
- Secret handling policy.
- Automatic patch apply.
- Moonlight contract changes.

## Evaluation Rubric

Judge agent/harness combinations by:

- scope discipline
- artifact quality
- code quality
- test behavior
- instruction following
- latency and cost
- recovery cost when wrong

The key question is not "which model is smartest." The key question is "which harness and model combination reduces commander token cost without lowering final project quality."
