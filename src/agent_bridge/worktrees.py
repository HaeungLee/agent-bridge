import datetime
import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


SCHEMA_VERSION = "worktree.v0"


@dataclass
class WorktreeInfo:
    run_id: str
    repo_root: Path
    worktree_path: Path
    base_ref: str
    base_sha: str
    branch_name: str
    created_at: str


def resolve_git_root(path: Path) -> Path:
    result = _run_git(path, ["rev-parse", "--show-toplevel"])
    return Path(result.stdout.strip()).resolve()


def resolve_head_sha(repo_root: Path, ref: str = "HEAD") -> str:
    result = _run_git(repo_root, ["rev-parse", ref])
    return result.stdout.strip()


def create_isolated_worktree(repo_root: Path, run_id: str, base_ref: str = "HEAD") -> WorktreeInfo:
    root = resolve_git_root(repo_root)
    base_sha = resolve_head_sha(root, base_ref)
    worktree_path = _default_worktree_path(run_id)
    if worktree_path.exists():
        raise FileExistsError(f"Worktree path already exists: {worktree_path}")

    _run_git(root, ["worktree", "add", "--detach", str(worktree_path), base_ref])
    return WorktreeInfo(
        run_id=run_id,
        repo_root=root,
        worktree_path=worktree_path.resolve(),
        base_ref=base_ref,
        base_sha=base_sha,
        branch_name=f"agent-bridge/{run_id}",
        created_at=datetime.datetime.now(datetime.UTC).isoformat(),
    )


def collect_worktree_changed_files(info: WorktreeInfo) -> list[str]:
    result = _run_git(info.worktree_path, ["status", "--porcelain=v1", "--untracked-files=all"])
    changed: set[str] = set()
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path:
            changed.add(path.replace("\\", "/"))
    return sorted(changed)


def export_worktree_patch(info: WorktreeInfo, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _stage_all_changes(info.worktree_path)
    result = _run_git(info.worktree_path, ["diff", "--binary", "--cached", "HEAD"])
    if not result.stdout:
        result = _run_git(info.worktree_path, ["diff", "--binary", "HEAD"])
    output_path.write_text(result.stdout, encoding="utf-8")


def remove_isolated_worktree(info: WorktreeInfo, force: bool = False) -> None:
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(info.worktree_path))
    try:
        _run_git(info.repo_root, args)
    except RuntimeError:
        if not force:
            raise
        if info.worktree_path.exists():
            shutil.rmtree(info.worktree_path)


def write_worktree_metadata(info: WorktreeInfo, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(info)
    data["schema_version"] = SCHEMA_VERSION
    data["repo_root"] = str(info.repo_root)
    data["worktree_path"] = str(info.worktree_path)
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _stage_all_changes(worktree_path: Path) -> None:
    _run_git(worktree_path, ["add", "-A"])


def _default_worktree_path(run_id: str) -> Path:
    safe_run_id = "".join(c for c in run_id if c.isalnum() or c in ("-", "_")).strip()
    if not safe_run_id:
        raise ValueError("run_id must contain at least one safe character")
    return Path(tempfile.gettempdir()) / "agent-bridge-worktrees" / safe_run_id


def _run_git(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=False,
        shell=False,
    )
    stdout = _decode_output(result.stdout)
    stderr = _decode_output(result.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}: {stderr.strip()}")
    return subprocess.CompletedProcess(result.args, result.returncode, stdout, stderr)


def _decode_output(value: bytes | None) -> str:
    if not value:
        return ""
    return value.decode("utf-8", errors="replace")
