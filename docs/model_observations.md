# Model Observations

Date: 2026-05-21

Purpose: record observed routing data for commander decisions. This is not a universal benchmark and should not be treated as a fixed ranking. Update only from actual project runs, reviews, or verified failures.

## Operating Principle

Use high-cost frontier models for judgment-heavy work:

- architecture decisions
- task decomposition
- safety gates
- final acceptance
- cross-agent review

Use lower-cost or faster agents for work-token-heavy tasks:

- scaffolding
- repetitive implementation
- repository inspection
- first-pass reports
- mock integrations
- narrow bug fixes

## Observations

### Codex / GPT-5.5

- Observed role: commander, reviewer, architecture and scope controller.
- Strengths observed: task decomposition, gate review, scope correction, risk identification, turning loose process logs into next-step plans.
- Risks observed: higher cost; can spend too much effort on direct implementation if not intentionally delegated.
- Recommended use: design, delegation packets, gate reviews, final acceptance, direct fixes after repeated subordinate-agent failure.

### Antigravity / Gemini 3.5

- Observed role: fast implementation worker inside Antigravity harness.
- Strengths observed: very high implementation speed, good response to narrow instructions, capable of scaffold and CLI implementation.
- Risks observed: strong scope drift; tends to continue into next phase or implement "obvious" follow-up work without a fresh instruction.
- Recommended use: narrow implementation tasks with explicit hard constraints and immediate process-log review.
- Guardrail: require "implement only this unit and stop" in every task.

### Antigravity / Sonnet 4.6

- Observed role: cleanup and feedback-resolution worker inside Antigravity harness.
- Strengths observed: good at applying review feedback and stabilizing earlier work.
- Risks observed: may over-complete workflow tasks, including repository management, if the harness frames work as end-to-end completion.
- Recommended use: focused cleanup, review feedback resolution, documentation polish, small safety fixes.
- Guardrail: explicitly forbid git operations unless requested for that turn.

### nanoGPT / Open-Source Large Models

- Observed role: not yet tested in this repository.
- Hypothesis: useful for lower-cost review, alternative designs, long-context investigation, or repetitive implementation after task-spec validation exists.
- Recommended next test: same narrow task spec across Gemini/Sonnet/nanoGPT models, judged by identical artifacts and acceptance checks.

## Current Routing Plan

Next experiment:

```text
Codex creates a narrow Phase 5 task spec.
Gemini, Sonnet, and one nanoGPT-hosted model receive comparable task specs.
agent-bridge records artifacts and verdicts.
Codex reviews process logs and compact reports only, then samples code as needed.
```

Primary metric is not raw intelligence. It is task suitability under the project workflow:

- scope discipline
- artifact correctness
- verification honesty
- implementation quality
- cost and latency
- ability to stop at assigned boundary
