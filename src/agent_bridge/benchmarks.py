import datetime
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "benchmark_evidence.v0"
DEFAULT_BENCHMARK_PATH = Path("docs") / "benchmarks" / "model_benchmarks.jsonl"
EVIDENCE_STATUSES = {"accepted_candidate", "qualified_observation", "rejected_candidate"}
DEFAULT_LIST_FIELDS = {"failure_modes"}


def benchmark_path(root: Path, explicit_path: str | None = None) -> Path:
    if explicit_path:
        path = Path(explicit_path)
        if not path.is_absolute():
            path = root / path
        return path
    return root / DEFAULT_BENCHMARK_PATH


def load_run_artifacts(root: Path, run_id: str) -> dict[str, Any]:
    run_dir = root / ".agent" / "runs" / run_id
    if not run_dir.exists() or not run_dir.is_dir():
        raise FileNotFoundError(f"Run directory does not exist: {run_id}")

    report = _read_json_object(run_dir / "decision_report.json")
    metrics = _read_json_object(run_dir / "metrics.json")
    touched_files = _read_json_list(run_dir / "touched_files.json")
    request = _read_json_object(run_dir / "request.json")
    return {
        "run_dir": run_dir,
        "report": report,
        "metrics": metrics,
        "touched_files": touched_files,
        "request": request,
        "final_report_exists": (run_dir / "final_report.md").exists(),
    }


def build_benchmark_record(
    *,
    root: Path,
    run_id: str,
    run_kind: str,
    evidence_status: str,
    harness: str,
    gate_status: str,
    instruction_following: str,
    scope_discipline: str,
    best_use_case: str,
    avoid_for: str,
    commander_notes: str,
    failure_modes: list[str] | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    if evidence_status not in EVIDENCE_STATUSES:
        raise ValueError(
            f"Invalid evidence_status '{evidence_status}'. Expected one of {sorted(EVIDENCE_STATUSES)}"
        )
    if not run_kind.strip():
        raise ValueError("run_kind is required")
    if not harness.strip():
        raise ValueError("harness is required")

    artifacts = load_run_artifacts(root, run_id)
    report = artifacts["report"]
    metrics = artifacts["metrics"]
    touched_files = artifacts["touched_files"]
    request = artifacts["request"]

    return {
        "schema_version": SCHEMA_VERSION,
        "recorded_at": datetime.date.today().isoformat(),
        "run_id": run_id,
        "task_id": task_id or _task_id_from_request(request),
        "run_kind": run_kind,
        "evidence_status": evidence_status,
        "agent": report.get("agent") or metrics.get("agent") or "unknown",
        "runner": report.get("runner") or metrics.get("runner") or "unknown",
        "harness": harness,
        "provider": report.get("provider") or metrics.get("provider") or "unknown",
        "model": report.get("model") or metrics.get("model") or "unknown",
        "runtime_seconds": _number_or_none(metrics.get("runtime_seconds")),
        "gate_status": gate_status,
        "changed_files_count": len(touched_files),
        "final_report": bool(artifacts["final_report_exists"]),
        "instruction_following": instruction_following,
        "scope_discipline": scope_discipline,
        "failure_modes": failure_modes or [],
        "best_use_case": best_use_case,
        "avoid_for": avoid_for,
        "commander_notes": commander_notes,
    }


def append_benchmark_record(path: Path, record: dict[str, Any], *, allow_duplicate: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_benchmark_records(path)
    if not allow_duplicate:
        for item in existing:
            if item.get("run_id") == record.get("run_id") and item.get("run_kind") == record.get("run_kind"):
                raise ValueError(
                    f"Benchmark record already exists for run_id={record.get('run_id')} "
                    f"run_kind={record.get('run_kind')}"
                )
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def read_benchmark_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"Benchmark record at {path}:{line_number} must be a JSON object")
        records.append(data)
    return records


def parse_failure_modes(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _task_id_from_request(request: dict[str, Any]) -> str:
    task = str(request.get("task") or "")
    if not task:
        return "unknown"
    path = Path(task)
    stem = path.stem
    return stem or task


def _number_or_none(value: Any) -> int | float | None:
    return value if isinstance(value, (int, float)) else None


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _read_json_list(path: Path) -> list[Any]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    return data if isinstance(data, list) else []
