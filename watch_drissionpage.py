import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
TARGET_SCRIPT = ROOT_DIR / "DrissionPage_example.py"


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def build_command(forwarded_args=None, python_executable=None, target_script=None):
    args = list(forwarded_args or [])
    python = python_executable or sys.executable
    script = Path(target_script or TARGET_SCRIPT).resolve()
    return [python, str(script), *args]


def stop_process(process, log_func=log):
    if process.poll() is not None:
        return

    log_func("Stopping child process.")
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        log_func("Child process did not exit after terminate(); killing it.")
        process.kill()
        process.wait(timeout=5)


def run_forever(command, cwd=None, restart_delay=2.0, popen_factory=None, sleep_func=time.sleep, log_func=log):
    launcher = popen_factory or (lambda cmd, cwd=None: subprocess.Popen(cmd, cwd=cwd))

    while True:
        process = None
        try:
            log_func(f"Starting child process: {' '.join(command)}")
            process = launcher(command, cwd=cwd)
            exit_code = process.wait()
            log_func(f"Child process exited with code {exit_code}. Restarting in {restart_delay} seconds.")
            sleep_func(restart_delay)
        except KeyboardInterrupt:
            log_func("Received Ctrl+C. Stopping watchdog.")
            if process is not None:
                stop_process(process, log_func=log_func)
            raise


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Watch DrissionPage_example.py and restart it after any exit.")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds to wait before restarting the child process.")
    parser.add_argument("target_args", nargs=argparse.REMAINDER, help="Arguments forwarded to DrissionPage_example.py. Prefix with --.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    forwarded_args = list(args.target_args)
    if forwarded_args[:1] == ["--"]:
        forwarded_args = forwarded_args[1:]

    if not TARGET_SCRIPT.is_file():
        raise FileNotFoundError(f"Target script not found: {TARGET_SCRIPT}")

    command = build_command(forwarded_args=forwarded_args)
    try:
        run_forever(command, cwd=str(ROOT_DIR), restart_delay=args.delay)
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
