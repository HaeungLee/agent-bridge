import subprocess
import sys
import time
import threading
from pathlib import Path

def read_stream(stream, name):
    try:
        # read char by char
        while True:
            char = stream.read(1)
            if not char:
                break
            # decode byte
            decoded = char.decode("utf-8", errors="replace")
            sys.stdout.write(decoded)
            sys.stdout.flush()
    except Exception as e:
        print(f"\n[{name} Reader Error] {e}")

def main():
    agy_path = r"C:\Users\Harry\AppData\Local\agy\bin\agy.exe"
    # Use absolute log path inside the workspace
    log_path = Path(r"W:\Projects\agent-bridge\tmp\test_agy.log")
    if log_path.exists():
        try:
            log_path.unlink()
        except Exception:
            pass

    cmd = [
        agy_path,
        "--dangerously-skip-permissions",
        "--log-file", str(log_path),
        "--print-timeout", "25s",
        "--print",
        "Reply with exactly: AGENT_BRIDGE_ANTIGRAVITY_SMOKE_OK"
    ]

    print(f"Running command: {' '.join(cmd)}")
    
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL, # Use DEVNULL to send immediate EOF and avoid hangs
        shell=False
    )

    t_out = threading.Thread(target=read_stream, args=(proc.stdout, "STDOUT"), daemon=True)
    t_err = threading.Thread(target=read_stream, args=(proc.stderr, "STDERR"), daemon=True)
    t_out.start()
    t_err.start()

    # Wait up to 60 seconds
    timeout = 60
    start = time.time()
    while proc.poll() is None:
        if time.time() - start > timeout:
            print(f"\n[TIMEOUT] Process did not exit within {timeout}s. Terminating...")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            break
        time.sleep(0.5)

    print(f"\nProcess exited with return code: {proc.returncode}")

    # Give a bit of time for threads to flush
    time.sleep(1)

    if log_path.exists():
        print(f"\n--- LOG FILE CONTENT ({log_path}) ---")
        log_content = log_path.read_text(encoding="utf-8", errors="replace")
        lines = log_content.splitlines()
        for l in lines[-60:]:
            print(l)
    else:
        print("\nLog file was not created!")

if __name__ == "__main__":
    main()
