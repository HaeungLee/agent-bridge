import os
from pathlib import Path
import tomllib
from typing import Dict, Any, Optional

def find_project_root() -> Path:
    """
    Finds the project root by searching upwards from the current file's directory
    until it finds a directory containing 'agent_bridge_mvp.md' or 'pyproject.toml'.
    Defaults to the current working directory if not found.
    """
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "agent_bridge_mvp.md").exists() or (parent / "pyproject.toml").exists():
            return parent
    return Path(os.getcwd())

def load_toml_config(file_path: Path) -> Dict[str, Any]:
    """
    Loads a single TOML configuration file.
    Returns an empty dictionary if the file does not exist.
    Raises exception if the file exists but has invalid TOML format or parsing errors.
    """
    if not file_path.exists():
        return {}
    with open(file_path, "rb") as f:
        try:
            return tomllib.load(f)
        except Exception as e:
            raise ValueError(f"Failed to parse TOML configuration '{file_path}': {e}") from e

def load_all_configs(root_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Loads all configurations (agents, runners, providers) from the config directory.
    """
    if root_path is None:
        root_path = find_project_root()
        
    config_dir = root_path / "config"
    
    return {
        "agents": load_toml_config(config_dir / "agents.toml"),
        "runners": load_toml_config(config_dir / "runners.toml"),
        "providers": load_toml_config(config_dir / "providers.toml")
    }
