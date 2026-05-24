import datetime
import json
import re
from pathlib import Path
from typing import Any

from agent_bridge.config import find_project_root
from agent_bridge.task_spec import load_task_spec


PROCESS_SOFT_LINE_LIMIT = 800


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for _ in f)


def process_path(root_path: Path, date: str, index: int = 1) -> Path:
    suffix = "" if index == 1 else str(index)
    return root_path / "docs" / "process" / f"{date}_process{suffix}.md"


def rollup_daily_runs(root_path: Path | None = None, date: str | None = None) -> Path | None:
    if root_path is None:
        root_path = find_project_root()
    if date is None:
        date = datetime.datetime.now().strftime("%Y%m%d")

    runs = _load_completed_runs(root_path, date)
    if not runs:
        return None

    process_dir = root_path / "docs" / "process"
    process_dir.mkdir(parents=True, exist_ok=True)

    existing_run_ids = _existing_rollup_run_ids(root_path, date)
    pending = [(run_dir, report) for run_dir, report in runs if report["run_id"] not in existing_run_ids]
    if not pending:
        return _active_process_path(root_path, date)

    target = _active_process_path(root_path, date)
    _ensure_process_header(target, date, _process_index(target, date))
    if _process_index(target, date) > 1:
        _ensure_file_index(root_path, date)

    blocks = _grouped_rollup_blocks(root_path, pending)
    with target.open("a", encoding="utf-8") as f:
        f.write(blocks)

    if count_lines(target) >= PROCESS_SOFT_LINE_LIMIT:
        _ensure_file_index(root_path, date)
    return target


def _load_completed_runs(root_path: Path, date: str) -> list[tuple[Path, dict[str, Any]]]:
    runs_dir = root_path / ".agent" / "runs"
    if not runs_dir.exists():
        return []

    runs: list[tuple[Path, dict[str, Any]]] = []
    for run_dir in sorted(runs_dir.iterdir(), key=lambda p: p.name):
        if not run_dir.is_dir() or not run_dir.name.startswith(date):
            continue
        if not (run_dir / "completed.marker").exists():
            continue
        report_path = run_dir / "decision_report.json"
        if not report_path.exists():
            continue
        try:
            report = json.loads(report_path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        if not isinstance(report, dict):
            continue
        report.setdefault("run_id", run_dir.name)
        runs.append((run_dir, report))
    return runs


def _active_process_path(root_path: Path, date: str) -> Path:
    index = 1
    while True:
        candidate = process_path(root_path, date, index)
        if not candidate.exists():
            if index > 1:
                _write_rollover_note(root_path, date, index)
            return candidate
        if count_lines(candidate) < PROCESS_SOFT_LINE_LIMIT:
            return candidate
        index += 1


def _write_rollover_note(root_path: Path, date: str, index: int) -> None:
    previous = process_path(root_path, date, index - 1)
    current = process_path(root_path, date, index)
    if previous.exists():
        note = f"\n\n<!-- Rollover to {current.name} -->\n"
        text = previous.read_text(encoding="utf-8")
        if note.strip() not in text:
            with previous.open("a", encoding="utf-8") as f:
                f.write(note)
    _ensure_file_index(root_path, date)


def _ensure_process_header(path: Path, date: str, index: int) -> None:
    if path.exists() and path.stat().st_size > 0:
        return
    title = f"# {date} Process" if index == 1 else f"# {date} Process {index}"
    lines = [title, ""]
    if index > 1:
        previous = process_path(path.parents[1].parent, date, index - 1)
        lines.append(f"<!-- Continued from {previous.name} -->")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _ensure_file_index(root_path: Path, date: str) -> None:
    first = process_path(root_path, date, 1)
    if not first.exists():
        return

    indices = _existing_process_indices(root_path, date)
    if len(indices) <= 1:
        return

    index_lines = ["## File Index", ""]
    for index in indices:
        path = process_path(root_path, date, index)
        label = "current day log" if index == 1 else f"continued log part {index}"
        index_lines.append(f"- `{path.name}`: {label}")
    index_lines.append("")
    replacement = "\n".join(index_lines)

    content = first.read_text(encoding="utf-8")
    pattern = re.compile(r"## File Index\n\n(?:- `.*`\: .*\n)+\n", re.MULTILINE)
    if pattern.search(content):
        content = pattern.sub(replacement + "\n", content, count=1)
    else:
        title_match = re.match(r"^# .+\n", content)
        insert_at = title_match.end() if title_match else 0
        content = content[:insert_at] + "\n" + replacement + content[insert_at:]
    first.write_text(content, encoding="utf-8")


def _existing_process_indices(root_path: Path, date: str) -> list[int]:
    indices: list[int] = []
    index = 1
    while True:
        path = process_path(root_path, date, index)
        if not path.exists():
            break
        indices.append(index)
        index += 1
    return indices


def _existing_rollup_run_ids(root_path: Path, date: str) -> set[str]:
    found: set[str] = set()
    pattern = re.compile(r"`(\d{8}-\d{6}-[A-Za-z0-9]+-[A-Za-z0-9_-]+)`")
    for index in _existing_process_indices(root_path, date):
        path = process_path(root_path, date, index)
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        found.update(pattern.findall(text))
    return found


def _grouped_rollup_blocks(root_path: Path, runs: list[tuple[Path, dict[str, Any]]]) -> str:
    groups: dict[str, list[tuple[Path, dict[str, Any]]]] = {}
    for run_dir, report in runs:
        milestone = _milestone_for_run(root_path, run_dir)
        groups.setdefault(milestone, []).append((run_dir, report))

    chunks: list[str] = []
    for milestone in sorted(groups):
        chunks.append(f"\n## Milestone: {milestone}\n\n### Runs\n\n")
        for run_dir, report in groups[milestone]:
            chunks.append(_run_block(root_path, run_dir, report))
    return "".join(chunks)


def _milestone_for_run(root_path: Path, run_dir: Path) -> str:
    request_path = run_dir / "request.json"
    task_path = ""
    try:
        request = json.loads(request_path.read_text(encoding="utf-8-sig"))
        task_path = str(request.get("task") or "")
    except Exception:
        return "Uncategorized Slices"
    if not task_path:
        return "Uncategorized Slices"

    spec_path = (root_path / task_path).with_suffix(".toml")
    if not spec_path.exists():
        return "Uncategorized Slices"
    try:
        spec = load_task_spec(spec_path)
    except Exception:
        return "Uncategorized Slices"
    return str(spec.get("milestone") or spec.get("phase") or "Uncategorized Slices")


def _run_block(root_path: Path, run_dir: Path, report: dict[str, Any]) -> str:
    run_id = str(report.get("run_id") or run_dir.name)
    time_label = _time_label(run_id)
    agent = str(report.get("agent") or "unknown")
    status = str(report.get("status") or "unknown")
    summary = str(report.get("summary") or "").strip() or "No summary provided."
    verdict = str(report.get("verdict") or "N/A")
    tests = report.get("tests")
    test_summary = tests.get("summary") if isinstance(tests, dict) else str(tests or "Not run.")
    files_changed = report.get("files_changed") if isinstance(report.get("files_changed"), list) else []
    risks = report.get("risks") if isinstance(report.get("risks"), list) else []

    request = _load_json(run_dir / "request.json")
    task = str(request.get("task") or "unknown") if isinstance(request, dict) else "unknown"

    changed_lines = "\n".join(f"  - `{item}`" for item in files_changed) if files_changed else "  - (None)"
    risk_lines = "\n".join(f"  - {item}" for item in risks) if risks else "  - (None)"
    rel_run = _repo_relative(root_path, run_dir)

    return f"""#### {time_label} - `{run_id}` - `{agent}` - `{task}`

- **Status**: {status}
- **Summary**: {summary}
- **Files changed**:
{changed_lines}
- **Tests**: {test_summary}
- **Risks**:
{risk_lines}
- **Commander verdict**: {verdict}
- **Artifacts**:
  - `{rel_run}/summary.md`
  - `{rel_run}/decision_report.json`

"""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _time_label(run_id: str) -> str:
    match = re.match(r"^\d{8}-(\d{2})(\d{2})\d{2}-", run_id)
    if not match:
        return "00:00"
    return f"{match.group(1)}:{match.group(2)}"


def _repo_relative(root_path: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root_path.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _process_index(path: Path, date: str) -> int:
    if path.name == f"{date}_process.md":
        return 1
    match = re.match(rf"^{date}_process(\d+)\.md$", path.name)
    if not match:
        return 1
    return int(match.group(1))
