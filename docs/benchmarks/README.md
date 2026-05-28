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

## Recording

Use `agent-bridge bench record` after commander review:

```powershell
uv run agent-bridge bench record `
  --run 20260524-192821-a39435-aider_deepseek_flash `
  --kind worktree_patch `
  --status accepted_candidate `
  --harness aider `
  --gate passed `
  --instruction good `
  --scope write_scope_only `
  --best-use "default cheap fast worktree_patch candidate for small scoped changes" `
  --avoid "large ambiguous refactors until broader evidence exists" `
  --notes "Fastest correct one-shot patch in the matrix."
```

The command reads run artifacts from `.agent/runs/<run_id>/` and appends one JSON
object to `docs/benchmarks/model_benchmarks.jsonl`. It refuses duplicate
`run_id` + `run_kind` records unless `--allow-duplicate` is passed.
