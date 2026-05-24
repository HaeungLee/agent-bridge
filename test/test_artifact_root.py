import json
from pathlib import Path

from agent_bridge.runs import execute_mock_run, resolve_artifact_root


def _write_minimal_project(root: Path) -> Path:
    (root / "config").mkdir(parents=True)
    (root / ".agent" / "tasks").mkdir(parents=True)
    (root / "config" / "agents.toml").write_text(
        """
[agents.mock_impl]
runner = "mock_subprocess"
provider = "local"
model = "mock"
role = "implementation"
default_mode = "mock"
""".strip(),
        encoding="utf-8",
    )
    (root / "config" / "runners.toml").write_text(
        """
[runners.mock_subprocess]
type = "subprocess"
command = "python"
""".strip(),
        encoding="utf-8",
    )
    (root / "config" / "providers.toml").write_text("", encoding="utf-8")
    task_path = root / ".agent" / "tasks" / "sample.md"
    task_path.write_text("Mock task\n", encoding="utf-8")
    return task_path


def test_resolve_artifact_root_defaults_to_project_root(tmp_path):
    assert resolve_artifact_root(tmp_path) == tmp_path


def test_resolve_artifact_root_prefers_explicit_path(tmp_path, monkeypatch):
    artifact_root = tmp_path / "artifact-root"
    monkeypatch.setenv("AGENT_BRIDGE_ARTIFACT_ROOT", str(tmp_path / "env-root"))

    assert resolve_artifact_root(tmp_path, artifact_root) == artifact_root.resolve()


def test_run_writes_artifacts_to_explicit_artifact_root(tmp_path):
    project_root = tmp_path / "worktree"
    artifact_root = tmp_path / "commander"
    project_root.mkdir()
    artifact_root.mkdir()
    task_path = _write_minimal_project(project_root)

    run_id = execute_mock_run(
        "mock_impl",
        task_path,
        project_root,
        root_path=project_root,
        artifact_root_path=artifact_root,
    )

    run_dir = artifact_root / ".agent" / "runs" / run_id
    assert run_dir.exists()
    assert not (project_root / ".agent" / "runs" / run_id).exists()
    request = json.loads((run_dir / "request.json").read_text(encoding="utf-8"))
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert request["artifact_root"] == str(artifact_root.resolve())
    assert metrics["workspace"] == str(project_root)
    assert (run_dir / "decision_report.json").exists()
    assert (run_dir / "completed.marker").exists()


def test_run_writes_artifacts_to_env_artifact_root(tmp_path, monkeypatch):
    project_root = tmp_path / "worktree"
    artifact_root = tmp_path / "commander"
    project_root.mkdir()
    artifact_root.mkdir()
    task_path = _write_minimal_project(project_root)
    monkeypatch.setenv("AGENT_BRIDGE_ARTIFACT_ROOT", str(artifact_root))

    run_id = execute_mock_run("mock_impl", task_path, project_root, root_path=project_root)

    assert (artifact_root / ".agent" / "runs" / run_id / "decision_report.json").exists()
    assert not (project_root / ".agent" / "runs" / run_id).exists()
