# Benchmark Evidence

This directory stores commander-curated benchmark evidence.

It is not a global model leaderboard. Each entry is evidence for a specific
task class, harness, provider, model, and run contract.

## Files

- `model_benchmarks.jsonl`: append-only JSON Lines benchmark records.

## Record Policy

Only record runs that are useful routing evidence:

- real model or real harness calls
- normalized run artifacts exist
- run directory is still available under `.agent/runs/`
- mock, placeholder, blocked, or lost transient runs are excluded

Use `evidence_status` to distinguish routing strength:

- `accepted_candidate`: good enough to consider for the task class
- `qualified_observation`: useful data, but with an important caveat
- `rejected_candidate`: real run that should steer routing away

Prefer task-class evidence over general model ranking. A model can be strong for
`worktree_patch` and weak for `readonly_report`, or the reverse.

