from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

@dataclass
class RunnerResult:
    status: str  # completed | failed | timeout | blocked
    exit_code: Optional[int]
    stdout: str
    stderr: str
    summary: str
    commands_run: List[str]
    runtime_seconds: float

class Runner:
    def run(self, task_path: Path, workspace_path: Path, timeout_seconds: int) -> RunnerResult:
        """
        Executes the delegated task on the target workspace.
        """
        raise NotImplementedError("Subclasses must implement run()")
