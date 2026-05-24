# Isolated Worktree Execution v0

Date: 2026-05-22

Status: commander-approved implementation design for the first isolated write-capable foundation.

## Goal

Add a small, testable git worktree utility layer before enabling write-capable subordinate agents.

This layer must let Agent Bridge create an isolated workspace, run only safe smoke operations there at first, export a patch, and remove the worktree without touching the active workspace.

## Non-Goals

Do not implement these in v0:

- Automatic patch application to the active workspace.
- Write-capable OpenCode, Antigravity, or raw API agent execution.
- Task-spec `read_scope` / `write_scope` migration.
- Full `agent-bridge run` worktree orchestration.
- Long-lived worktree pooling.
- Branch publication or commits.

## Default Policy

The default write-capable isolation unit is a git worktree.

Subordinate write tasks must not edit the commander's active workspace. They should run in a temporary worktree and export a standard patch artifact for commander review.

## Directory Policy

Worktrees should be created outside the active repository tree by default.

Recommended location:

```text
<system temp>/agent-bridge-worktrees/<run_id>/
```

The run directory remains under:

```text
.agent/runs/<run_id>/
```

The run directory records worktree metadata and exported patch artifacts. The temporary worktree can be removed after patch export unless `keep=True` is requested for debugging.

For delegated runs launched from a temporary or subordinate worktree, the execution workspace and the persistent artifact root may be separated. The execution workspace is where the runner reads and writes project files. The artifact root is where Agent Bridge writes durable commander-facing run artifacts:

```text
agent-bridge run --workspace <execution-workspace> --artifact-root <commander-project-root>
```

The same override is available for automation:

```text
AGENT_BRIDGE_ARTIFACT_ROOT=<commander-project-root>
```

When unset, the artifact root defaults to the project root detected by the running process, preserving the original behavior. This explicit artifact-root contract is preferred over copying `.agent/runs/` out of a worktree during teardown because it avoids trusting a later synchronization step and keeps run artifacts durable from the start.

## Module

Add:

```text
src/agent_bridge/worktrees.py
```

Suggested public API:

```python
@dataclass
class WorktreeInfo:
    run_id: str
    repo_root: Path
    worktree_path: Path
    base_ref: str
    base_sha: str
    branch_name: str

def resolve_git_root(path: Path) -> Path
def resolve_head_sha(repo_root: Path) -> str
def create_isolated_worktree(repo_root: Path, run_id: str, base_ref: str = "HEAD") -> WorktreeInfo
def export_worktree_patch(info: WorktreeInfo, output_path: Path) -> None
def collect_worktree_changed_files(info: WorktreeInfo) -> list[str]
def remove_isolated_worktree(info: WorktreeInfo, force: bool = False) -> None
def write_worktree_metadata(info: WorktreeInfo, output_path: Path) -> None
```

## Git Commands

Use `subprocess.run([...], shell=False)` for all git commands.

Create:

```text
git -C <repo_root> rev-parse --show-toplevel
git -C <repo_root> rev-parse <base_ref>
git -C <repo_root> worktree add --detach <worktree_path> <base_ref>
```

Diff:

```text
git -C <worktree_path> status --porcelain=v1 --untracked-files=all
git -C <worktree_path> diff --binary HEAD
git -C <worktree_path> ls-files --others --exclude-standard
```

Patch export must include tracked modifications and untracked files. Because `git diff --binary HEAD` does not include untracked files, v0 may either:

- add untracked files to the worktree index before diff export, then run `git diff --binary --cached HEAD`; or
- export a separate untracked file manifest and leave untracked-file patching to a later version.

Preferred v0 behavior: include untracked files in `patch.diff` by staging only inside the isolated worktree, then exporting a cached binary diff. This does not touch the active workspace.

Remove:

```text
git -C <repo_root> worktree remove <worktree_path>
```

If remove fails and `force=True`:

```text
git -C <repo_root> worktree remove --force <worktree_path>
```

## Metadata Artifact

Write:

```text
.agent/runs/<run_id>/worktree.json
```

Shape:

```json
{
  "schema_version": "worktree.v0",
  "run_id": "20260522-...",
  "repo_root": "W:/Projects/agent-bridge",
  "worktree_path": "C:/Users/.../Temp/agent-bridge-worktrees/20260522-...",
  "base_ref": "HEAD",
  "base_sha": "<sha>",
  "branch_name": "agent-bridge/<run_id>",
  "created_at": "<iso timestamp>"
}
```

## Patch Artifact

Write:

```text
.agent/runs/<run_id>/patch.diff
```

Patch export rules:

- Use binary-safe git diff.
- Include untracked files for v0 if practical by staging inside the worktree only.
- Do not commit.
- Do not modify the active workspace.
- If no changes exist, write an empty patch file and report `0 files changed`.

## Dirty Active Workspace Policy

V0 should not require the active workspace to be clean for helper smoke tests.

For real write-capable agent execution later:

- The commander must choose whether to base the worktree on `HEAD` or another explicit ref.
- Uncommitted active workspace changes are not copied into the worktree by default.
- If a task depends on uncommitted user changes, the commander must choose a separate policy.

## Failure Modes

All helper failures should raise clear exceptions with git stderr included:

- Not inside a git repository.
- Worktree path already exists.
- Base ref cannot be resolved.
- Worktree add fails.
- Patch export fails.
- Worktree remove fails.

The caller is responsible for turning these into run artifacts.

## Verification

The first implementation task should verify only helper behavior using local git and mock-safe operations.

Suggested smoke:

1. Create an isolated worktree from `HEAD`.
2. Write or modify a temporary file inside the isolated worktree only.
3. Export `patch.diff`.
4. Confirm active workspace does not contain that temporary file.
5. Remove the worktree.
6. Run `uv run python -m compileall src`.
7. Run `uv run agent-bridge doctor`.

## First Implementation Slice

Implement only:

- `src/agent_bridge/worktrees.py`
- unit/smoke helper functions as needed
- a narrow task spec for the implementation if needed

Do not wire worktrees into `agent-bridge run` yet.

## Phase 5-D Gate Foundation

`task_spec.v0` now supports a narrow execution mode split:

```toml
execution_mode = "report"
execution_mode = "worktree_patch"
```

`report` remains the safe default. `worktree_patch` requires explicit `write_scope` and makes `agent-bridge task gate` require both:

```text
patch.diff
worktree.json
```

The gate validates that `worktree.json` is parseable, uses `schema_version = "worktree.v0"`, and matches the run directory ID. It also parses changed paths from `patch.diff` and checks them against `write_scope` and `forbidden_files`.

At Phase 5-D this was still a gate foundation only: worktree lifecycle orchestration was not wired into `agent-bridge run`, and patches were not automatically applied.

## Phase 5-E Run Orchestration Foundation

`agent-bridge run` now detects a sibling task spec next to the rendered task prompt:

```text
.agent/tasks/example.md
.agent/tasks/example.toml
```

When the task spec declares:

```toml
execution_mode = "worktree_patch"
```

the run lifecycle creates an isolated git worktree before invoking the configured runner. The runner receives the isolated worktree path as its workspace, not the active commander workspace.

After runner execution, the lifecycle exports:

```text
.agent/runs/<run_id>/worktree.json
.agent/runs/<run_id>/patch.diff
```

The worktree is removed by default after patch export. Set `AGENT_BRIDGE_KEEP_WORKTREE=1` to keep the temporary worktree for debugging.

Patches are still not applied automatically. The commander must run the task gate, inspect the patch, and decide whether to apply it.

If a subordinate agent invokes Agent Bridge from inside its own temporary worktree, it should pass the commander's artifact root explicitly:

```text
uv run agent-bridge run --agent <agent> --task <task.md> --workspace . --artifact-root W:\Projects\agent-bridge
```

The resulting run directory is then written under:

```text
W:\Projects\agent-bridge\.agent\runs\<run_id>\
```

while the runner still receives the subordinate worktree as its execution workspace.

## Failure Artifact Policy

If worktree orchestration fails after a run directory has been created, Agent Bridge should still write commander-readable artifacts whenever feasible:

```text
decision_report.json
summary.md
process.md
metrics.json
touched_files.json
diffstat.txt
tests.md
risks.md
raw/stdout.txt
raw/stderr.txt
completed.marker
orchestration_errors.json
```

Typical failures include:

- workspace is not a git repository
- worktree creation fails
- runner configuration fails after run directory creation
- patch export fails
- worktree cleanup fails

If cleanup fails after runner execution, the run is treated as failed because isolated write-capable execution cannot be trusted until the leftover workspace is inspected or removed.
