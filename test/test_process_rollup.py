import json
from pathlib import Path

from agent_bridge.process import count_lines, process_path, rollup_daily_runs


def _write_run(root: Path, run_id: str, task: str = ".agent/tasks/sample.md") -> Path:
    run_dir = root / ".agent" / "runs" / run_id
    (run_dir / "raw").mkdir(parents=True)
    (run_dir / "completed.marker").write_text("{}", encoding="utf-8")
    (run_dir / "request.json").write_text(
        json.dumps({"task": task, "workspace": str(root)}, indent=2),
        encoding="utf-8",
    )
    (run_dir / "summary.md").write_text("# Summary\n", encoding="utf-8")
    (run_dir / "decision_report.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "agent": "mock_impl",
                "status": "completed",
                "summary": "Mock summary",
                "files_changed": ["src/example.py"],
                "tests": {"status": "not_run", "summary": "Not run."},
                "risks": ["Low risk"],
                "verdict": "NEEDS_DECISION",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return run_dir


def test_count_lines_missing(tmp_path):
    assert count_lines(tmp_path / "missing.md") == 0


def test_rollup_uses_request_task_and_relative_artifacts(tmp_path):
    root = tmp_path
    (root / "docs" / "process").mkdir(parents=True)
    (root / ".agent" / "tasks").mkdir(parents=True)
    (root / ".agent" / "runs").mkdir(parents=True)
    (root / ".agent" / "tasks" / "sample.toml").write_text(
        'phase = "Phase 5-B"\n',
        encoding="utf-8",
    )
    _write_run(root, "20260524-120000-abcdef-mock_impl")

    target = rollup_daily_runs(root, "20260524")

    assert target == process_path(root, "20260524")
    text = target.read_text(encoding="utf-8")
    assert "## Milestone: Phase 5-B" in text
    assert "20260524-120000-abcdef-mock_impl" in text
    assert "`.agent/runs/20260524-120000-abcdef-mock_impl/summary.md`" in text
    assert "file:///" not in text


def test_rollup_deduplicates_across_parts(tmp_path):
    root = tmp_path
    (root / "docs" / "process").mkdir(parents=True)
    (root / ".agent" / "runs").mkdir(parents=True)
    run_id = "20260524-120000-abcdef-mock_impl"
    process_path(root, "20260524").write_text(f"# 20260524 Process\n\n#### 12:00 - `{run_id}`\n", encoding="utf-8")
    process_path(root, "20260524", 2).write_text("# 20260524 Process 2\n\n", encoding="utf-8")
    _write_run(root, run_id)

    target = rollup_daily_runs(root, "20260524")

    assert target is not None
    combined = process_path(root, "20260524").read_text(encoding="utf-8")
    combined += process_path(root, "20260524", 2).read_text(encoding="utf-8")
    assert combined.count(run_id) == 1


def test_rollup_rolls_over_at_soft_limit(tmp_path):
    root = tmp_path
    (root / "docs" / "process").mkdir(parents=True)
    (root / ".agent" / "runs").mkdir(parents=True)
    process_path(root, "20260524").write_text("# 20260524 Process\n" + ("line\n" * 800), encoding="utf-8")
    _write_run(root, "20260524-130000-abcdef-mock_impl")

    target = rollup_daily_runs(root, "20260524")

    assert target == process_path(root, "20260524", 2)
    assert target.exists()
    assert "20260524-130000-abcdef-mock_impl" in target.read_text(encoding="utf-8")
    first = process_path(root, "20260524").read_text(encoding="utf-8")
    assert "## File Index" in first
    assert "`20260524_process2.md`" in first
