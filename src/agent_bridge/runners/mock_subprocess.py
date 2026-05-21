import sys
import subprocess
import time
from pathlib import Path
from agent_bridge.runners.base import Runner, RunnerResult

class MockSubprocessRunner(Runner):
    def run(self, task_path: Path, workspace_path: Path, timeout_seconds: int) -> RunnerResult:
        start_time = time.time()
        
        # 1. Check for timeout trigger in task name or content safely
        trigger_timeout = False
        if "timeout" in task_path.name.lower():
            trigger_timeout = True
        else:
            try:
                with open(task_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "TIMEOUT_TRIGGER" in content:
                        trigger_timeout = True
            except Exception:
                pass
                
        # 2. Prepare safe python inline script
        # sys.argv[1]: task_path
        # sys.argv[2]: workspace_path
        # sys.argv[3]: trigger_timeout_flag
        inline_script = (
            "import sys, time\n"
            "task = sys.argv[1]\n"
            "workspace = sys.argv[2]\n"
            "trigger = sys.argv[3] == 'True'\n"
            "if trigger:\n"
            "    time.sleep(10)\n"
            "print('mock_subprocess runner executed')\n"
            "print(f'task={task}')\n"
            "print(f'workspace={workspace}')\n"
            "sys.exit(0)\n"
        )
        
        args = [
            sys.executable,
            "-c",
            inline_script,
            str(task_path),
            str(workspace_path),
            str(trigger_timeout)
        ]
        
        # Format command list to a simplified display representation
        workspace_display = workspace_path.name if workspace_path.name else str(workspace_path)
        command_display = f"{Path(sys.executable).name} -c <inline_script> {task_path.name} {workspace_display} {trigger_timeout}"
        commands_run = [command_display]
        
        try:
            res = subprocess.run(
                args,
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )
            runtime = time.time() - start_time
            
            return RunnerResult(
                status="completed",
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
                summary="Mock subprocess runner executed successfully.",
                commands_run=commands_run,
                runtime_seconds=round(runtime, 4)
            )
            
        except subprocess.TimeoutExpired as e:
            runtime = time.time() - start_time
            # Get captured stdout/stderr if populated in exception
            captured_stdout = e.stdout if isinstance(e.stdout, str) else (e.stdout.decode("utf-8", errors="ignore") if e.stdout else "")
            captured_stderr = e.stderr if isinstance(e.stderr, str) else (e.stderr.decode("utf-8", errors="ignore") if e.stderr else "")
            
            timeout_msg = f"Subprocess timed out after {timeout_seconds} seconds."
            full_stderr = f"{captured_stderr}\n{timeout_msg}".strip() if captured_stderr else timeout_msg
            
            return RunnerResult(
                status="timeout",
                exit_code=None,
                stdout=captured_stdout,
                stderr=full_stderr,
                summary=f"Mock subprocess runner timed out after {timeout_seconds}s.",
                commands_run=commands_run,
                runtime_seconds=round(runtime, 4)
            )
            
        except Exception as e:
            runtime = time.time() - start_time
            return RunnerResult(
                status="failed",
                exit_code=-1,
                stdout="",
                stderr=str(e),
                summary=f"Mock subprocess runner failed: {e}",
                commands_run=commands_run,
                runtime_seconds=round(runtime, 4)
            )
