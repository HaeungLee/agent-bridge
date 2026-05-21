# Operating Policy for Commander and Subordinate Agents

Welcome, Agent. If you are reading this, you have been delegated a task within this repository. To maintain high engineering quality and prevent context contamination, you MUST adhere to the following rules.

## 1. General Principles

- **Read the Canonical Plan First**: Always read `agent_bridge_mvp.md` before making any structural or architectural decisions. It is the single source of truth for design direction.
- **Do Not Split or Rewrite the Plan**: Keep `agent_bridge_mvp.md` as one single, canonical file. Do not partition it by date, phase, or agent.
- **Roadmap as Execution State**: Treat `roadmap.md` as mutable execution state. Use it to track phases, milestones, active tasks, and blockers.
- **No Direct Commits**: Never run git commits unless explicitly instructed by the human supervisor.
- **No Repository Initialization**: Never run `git init`, create a repository, or alter repository metadata unless explicitly instructed by the human supervisor.
- **Prefer Structured Artifacts**: Prefer reading compact structured summaries (`summary.md` and `decision_report.json`) over raw logs or broad codebases.
- **Stay Inside the Assigned Scope**: Implement only the phase, milestone, or task explicitly assigned. Do not implement the next phase, even if it appears obvious or easy.
- **Stop After the Requested Unit**: After completing the assigned unit, update the process log and stop. Do not continue into "recommended next steps" without a new instruction.

## 2. Workspace Safety Policy

- **No Direct Workspace Modification**: Subagents must not edit the commander's active working tree directly by default.
- **Work in Isolation**: Subagents must edit only an isolated temporary workspace, temporary directory, or dedicated git worktree set up by `agent-bridge`.
- **Patch-based Export**: All code modifications must be exported as standard `.diff` patches rather than direct codebase mutators.
- **Approval is Required**: The commander agent must decide whether to apply the patch to the active workspace only after checking verification reports. No auto-apply is allowed.

## 3. Delegation Mechanics

Once the `agent-bridge` command-line utility is available, you must use it to delegate tasks to other subagents.

```powershell
# Run diagnostics before operations
agent-bridge doctor

# Delegate a task to an agent
agent-bridge run --agent <agent_name> --task <task_file_path> --workspace <target_workspace_path>
```

Keep your narratives clean and your processes strictly isolated. Let the lower-cost agents spend the tokens on implementation, and higher-quality agents spend the tokens on judgment.

## 4. Scope Control

Subordinate agents must treat scope control as a correctness requirement.

- Do not mark future roadmap milestones complete unless they were explicitly assigned.
- Do not create implementation plans for future phases unless asked.
- Do not add new CLI commands, runners, validators, or workflow features outside the requested task.
- If you notice a useful next step, record it under "Next recommended step" in the process log instead of implementing it.
- If instructions conflict, prefer the narrower instruction.
- If unsure whether something is in scope, stop and report the question.

## 5. Generated Artifacts

- Dynamic run outputs belong under `.agent/runs/`.
- Generated routing memory belongs under `.agent/metrics/`.
- Do not treat generated artifacts as source code unless explicitly instructed.
- When updating human-readable generated files, use valid UTF-8 and avoid mojibake.
