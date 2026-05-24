import json
import os
from pathlib import Path
import pytest
from agent_bridge.adapters import aider_adapter


def test_first_filesystem_scope():
    constraints = {"filesystem_scope": ["/workspace/path/test"]}
    scope = aider_adapter._first_filesystem_scope(constraints)
    assert scope == "/workspace/path/test"

    empty_constraints = {}
    assert aider_adapter._first_filesystem_scope(empty_constraints) == ""


def test_resolve_command(tmp_path):
    # Test fallback resolve when executable not in path
    cmd = aider_adapter._resolve_command("non_existent_command_xyz")
    assert cmd == "non_existent_command_xyz"


def test_load_env_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("NANOGPT_API_KEY=sk-test-nanogpt-key\nANOTHER_VAR=value\n# Comment\n", encoding="utf-8")
    
    loaded = aider_adapter._load_env_file(tmp_path)
    # Check that another variable not present in system .env is correctly loaded
    assert loaded.get("ANOTHER_VAR") == "value"
    # Verify that NANOGPT_API_KEY is extracted as a non-empty string
    assert len(loaded.get("NANOGPT_API_KEY", "")) > 0



def test_prepare_subprocess_command():
    cmd = ["aider", "--version"]
    prepared = aider_adapter._prepare_subprocess_command(cmd)
    # On non-Windows it remains unchanged
    if os.name != "nt":
        assert prepared == cmd
    else:
        # On Windows it stays as is unless suffix is bat/cmd/ps1
        assert prepared == cmd
