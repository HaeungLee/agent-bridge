import json
from pathlib import Path

import pytest

from agent_bridge.cli import cmd_compare


def _write_run(
    root: Path,
    run_id: str,
    *,
    model: str = "mock-model",
    runner: str = "mock-runner",
    status: str = "completed",
    runtime: float = 1.25,
    cost: float = 0.0,
    touched_files: list[str] | None = None,
    risks: list[str] | None = None,
    final_report: bool = False,
    verdict: str = "NEEDS_DECISION",
) -> Path:
    run_dir = root / ".agent" / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "completed.marker").write_text("{}", encoding="utf-8")
    (run_dir / "decision_report.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "model": model,
                "runner": runner,
                "status": status,
                "risks": risks or [],
                "verdict": verdict,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "metrics.json").write_text(
        json.dumps(
            {
                "runtime_seconds": runtime,
                "estimated_cost_usd": cost,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "touched_files.json").write_text(
        json.dumps(touched_files or [], indent=2),
        encoding="utf-8",
    )
    if final_report:
        (run_dir / "final_report.md").write_text("# Final\n", encoding="utf-8")
    return run_dir


class _Args:
    def __init__(self, runs: list[str]):
        self.runs = runs


def test_compare_prints_core_run_fields(tmp_path, monkeypatch, capsys):
    root = tmp_path
    (root / ".agent" / "runs").mkdir(parents=True)
    _write_run(
        root,
        "20260524-120000-aaaaaa-run_a",
        model="model-a",
        runner="runner-a",
        runtime=1.234,
        cost=0.01234,
        touched_files=["src/a.py"],
        risks=["risk-a"],
        final_report=True,
    )
    _write_run(
        root,
        "20260524-121000-bbbbbb-run_b",
        model="model-b",
        runner="runner-b",
        runtime=5.0,
        cost=0.0,
        touched_files=["src/b.py", "test/test_b.py"],
        risks=[],
    )
    monkeypatch.setattr("agent_bridge.cli.find_project_root", lambda: root)

    with pytest.raises(SystemExit) as excinfo:
        cmd_compare(_Args(["20260524-120000-aaaaaa-run_a", "20260524-121000-bbbbbb-run_b"]))

    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "Agent Bridge Run Compare" in out
    assert "model-a" in out
    assert "model-b" in out
    assert "runner-a" in out
    assert "runner-b" in out
    assert "1.23s" in out
    assert "5.00s" in out
    assert "$0.0123" in out
    assert "Final Report" in out
    assert "yes" in out
    assert "no" in out
    assert "src/a.py" in out
    assert "test/test_b.py" in out
    assert "risk-a" in out


def test_compare_handles_missing_optional_artifacts(tmp_path, monkeypatch, capsys):
    root = tmp_path
    (root / ".agent" / "runs").mkdir(parents=True)
    run_a = root / ".agent" / "runs" / "20260524-120000-aaaaaa-run_a"
    run_b = root / ".agent" / "runs" / "20260524-121000-bbbbbb-run_b"
    run_a.mkdir(parents=True)
    run_b.mkdir(parents=True)
    (run_a / "decision_report.json").write_text("{not-json", encoding="utf-8")
    (run_b / "decision_report.json").write_text(
        json.dumps({"status": "completed", "model": "model-b"}),
        encoding="utf-8",
    )
    monkeypatch.setattr("agent_bridge.cli.find_project_root", lambda: root)

    with pytest.raises(SystemExit) as excinfo:
        cmd_compare(_Args([run_a.name, run_b.name]))

    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "UNKNOWN" in out
    assert "model-b" in out
    assert "unknown" in out
    assert "Touched files:" in out
    assert "Risks:" in out


def test_compare_fails_for_missing_run(tmp_path, monkeypatch, capsys):
    root = tmp_path
    (root / ".agent" / "runs").mkdir(parents=True)
    _write_run(root, "20260524-120000-aaaaaa-run_a")
    monkeypatch.setattr("agent_bridge.cli.find_project_root", lambda: root)

    with pytest.raises(SystemExit) as excinfo:
        cmd_compare(_Args(["20260524-120000-aaaaaa-run_a", "missing-run"]))

    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "Error resolving runs" in err
    assert "missing-run" in err
