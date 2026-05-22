# Task: Review model routing memory redesign

## Metadata

- Schema: task_spec.v0
- Task ID: commander-model-routing-redesign
- Phase: Phase 5 Follow-up
- Slice: Routing Memory Design
- Owner: commander

## Objective

Inspect the current model routing memory implementation and propose a minimal design that separates generated routing notes from benchmark evidence. Focus on whether model_routing.md should remain generated, how to filter mock/smoke/placeholder runs, and what fields are needed for future benchmark evidence.

## Allowed Files

- docs/commander_handbook.md
- .agent/metrics/model_routing.md
- src/agent_bridge/evaluator.py
- src/agent_bridge/cli.py
- config/agents.toml
- docs/process/20260521_process.md
- docs/process/20260522_process.md
- .agent/tasks/commander_model_routing_redesign.toml
- .agent/tasks/commander_model_routing_redesign.md

## Forbidden Files

- docs/plan/agent_bridge_mvp.md
- .git/**
- .agent/runs/**
- .agent/sessions/*.json

## Required Commands

- uv run agent-bridge task validate --spec .agent/tasks/commander_model_routing_redesign.toml
- uv run agent-bridge task render --spec .agent/tasks/commander_model_routing_redesign.toml --out .agent/tasks/commander_model_routing_redesign.md

## Acceptance Criteria

- Report whether model_routing.md is generated or source-managed state.
- Explain why glm-5.2 entries are not reliable real-model evidence.
- Recommend fields or filters for benchmark evidence.
- Do not modify files.

## Hard Rules

- Do not commit.
- Do not implement the next phase.
- Do not modify files.
- Do not self-declare Commander Verdict or PASS.

## Expected Report

- Changed files
- Commands run
- Result
- Risks
- Open questions
- Next recommended step

## Execution Boundary

Implement only the task described above. Do not implement future phases, adjacent features, or optional integrations.
If a required change appears to exceed the allowed files or hard rules, stop and report the blocker.
