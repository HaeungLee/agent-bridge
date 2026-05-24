import json

from agent_bridge.task_spec import check_run_patch


def _spec() -> dict:
    return {
        "schema_version": "task_spec.v0",
        "task_id": "patch-gate-test",
        "phase": "Test",
        "slice": "Patch Gate",
        "title": "Patch gate test",
        "owner": "test",
        "execution_mode": "worktree_patch",
        "objective": "Validate patch gate behavior.",
        "allowed_files": ["scratch/example.py"],
        "read_scope": ["scratch/example.py"],
        "write_scope": ["scratch/example.py"],
        "forbidden_files": [".git/**"],
        "required_commands": ["pytest"],
        "acceptance_criteria": ["Patch is valid."],
        "hard_rules": ["Do not commit.", "Do not implement the next phase."],
        "expected_report_sections": ["Result"],
    }


def _write_worktree_metadata(run_dir):
    (run_dir / "worktree.json").write_text(
        json.dumps(
            {
                "schema_version": "worktree.v0",
                "run_id": run_dir.name,
                "repo_root": "repo",
                "worktree_path": "worktree",
                "base_ref": "HEAD",
                "base_sha": "abc123",
            }
        ),
        encoding="utf-8",
    )


def test_worktree_patch_rejects_empty_patch(tmp_path):
    run_dir = tmp_path / "20260524-000000-empty"
    run_dir.mkdir()
    _write_worktree_metadata(run_dir)
    (run_dir / "patch.diff").write_text("", encoding="utf-8")

    result = check_run_patch(_spec(), run_dir)

    assert not result.passed
    assert "patch.diff contains no changed files" in result.patch_errors


def test_worktree_patch_accepts_changed_file_in_scope(tmp_path):
    run_dir = tmp_path / "20260524-000001-changed"
    run_dir.mkdir()
    _write_worktree_metadata(run_dir)
    (run_dir / "patch.diff").write_text(
        "\n".join(
            [
                "diff --git a/scratch/example.py b/scratch/example.py",
                "new file mode 100644",
                "index 0000000..1234567",
                "--- /dev/null",
                "+++ b/scratch/example.py",
                "@@ -0,0 +1 @@",
                "+value = 1",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = check_run_patch(_spec(), run_dir)

    assert result.passed
    assert result.changed_files == ["scratch/example.py"]
