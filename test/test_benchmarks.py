import json
from pathlib import Path

import pytest

from agent_bridge.benchmarks import (
    append_benchmark_record,
    benchmark_path,
    build_benchmark_record,
    read_benchmark_records,
)
from agent_bridge.cli import cmd_bench_record


def _write_run(root: Path, run_id: str = "20260528-120000-aaaaaa-agent") -> Path:
    run_dir = root / ".agent" / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "decision_report.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "agent": "aider_deepseek_flash",
                "runner": "cli_adapter",
                "provider": "nanogpt",
                "model": "openai/deepseek/deepseek-v4-flash",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "metrics.json").write_text(
        json.dumps({"runtime_seconds": 9.5}),
        encoding="utf-8",
    )
    (run_dir / "touched_files.json").write_text(
        json.dumps(["scratch/aider_patch_probe.py"]),
        encoding="utf-8",
    )
    (run_dir / "request.json").write_text(
        json.dumps({"task": ".agent/tasks/bench_worktree_patch_latency_classifier.md"}),
        encoding="utf-8",
    )
    (run_dir / "final_report.md").write_text("final\n", encoding="utf-8")
    return run_dir


def test_build_benchmark_record_from_run_artifacts(tmp_path):
    run_id = "20260528-120000-aaaaaa-agent"
    _write_run(tmp_path, run_id)

    record = build_benchmark_record(
        root=tmp_path,
        run_id=run_id,
        run_kind="worktree_patch",
        evidence_status="accepted_candidate",
        harness="aider",
        gate_status="passed",
        instruction_following="good",
        scope_discipline="write_scope_only",
        best_use_case="small patch",
        avoid_for="large refactor",
        commander_notes="Fast and correct.",
        failure_modes=["none_observed"],
    )

    assert record["schema_version"] == "benchmark_evidence.v0"
    assert record["task_id"] == "bench_worktree_patch_latency_classifier"
    assert record["agent"] == "aider_deepseek_flash"
    assert record["runtime_seconds"] == 9.5
    assert record["changed_files_count"] == 1
    assert record["final_report"] is True
    assert record["failure_modes"] == ["none_observed"]


def test_append_benchmark_record_rejects_duplicate_run_kind(tmp_path):
    path = tmp_path / "docs" / "benchmarks" / "model_benchmarks.jsonl"
    record = {
        "schema_version": "benchmark_evidence.v0",
        "run_id": "run-1",
        "run_kind": "worktree_patch",
    }

    append_benchmark_record(path, record)

    with pytest.raises(ValueError, match="already exists"):
        append_benchmark_record(path, record)

    assert read_benchmark_records(path) == [record]


class _Args:
    run = "20260528-120000-aaaaaa-agent"
    kind = "worktree_patch"
    status = "accepted_candidate"
    harness = "aider"
    gate = "passed"
    instruction = "good"
    scope = "write_scope_only"
    best_use = "small patch"
    avoid = "large refactor"
    notes = "Fast and correct."
    failures = ""
    task_id = None
    out = "tmp_benchmarks.jsonl"
    allow_duplicate = False


def test_cmd_bench_record_appends_jsonl(tmp_path, monkeypatch, capsys):
    _write_run(tmp_path)
    monkeypatch.setattr("agent_bridge.cli.find_project_root", lambda: tmp_path)

    with pytest.raises(SystemExit) as excinfo:
        cmd_bench_record(_Args())

    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "benchmark evidence appended" in out
    records = read_benchmark_records(benchmark_path(tmp_path, _Args.out))
    assert len(records) == 1
    assert records[0]["model"] == "openai/deepseek/deepseek-v4-flash"
