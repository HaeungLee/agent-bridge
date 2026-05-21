# Operating Policy for Commander and Subordinate Agents

Welcome, Agent. If you are reading this, you have been delegated a task within this repository. To maintain high engineering quality and prevent context contamination, you MUST adhere to the following rules.

## 1. General Principles

- **Read the Canonical Plan First**: Always read `agent_bridge_mvp.md` before making any structural or architectural decisions. It is the single source of truth for design direction.
- **Do Not Split or Rewrite the Plan**: Keep `agent_bridge_mvp.md` as one single, canonical file. Do not partition it by date, phase, or agent.
- **Roadmap as Execution State**: Treat `roadmap.md` as mutable execution state. Use it to track phases, milestones, active tasks, and blockers.
- **No Direct Commits**: Never run git commits unless explicitly instructed by the human supervisor.
- **Prefer Structured Artifacts**: Prefer reading compact structured summaries (`summary.md` and `decision_report.json`) over raw logs or broad codebases.

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
