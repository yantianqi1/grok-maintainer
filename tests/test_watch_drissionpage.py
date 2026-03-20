import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "watch_drissionpage.py"


def load_watchdog_module():
    if not MODULE_PATH.exists():
        return None

    spec = importlib.util.spec_from_file_location("watch_drissionpage", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeProcess:
    def __init__(self, returncode=0, interrupt_on_wait=False):
        self.returncode = None
        self.final_returncode = returncode
        self.interrupt_on_wait = interrupt_on_wait
        self.wait_calls = []
        self.terminate_calls = 0
        self.kill_calls = 0

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        if timeout is None and self.interrupt_on_wait:
            raise KeyboardInterrupt()
        if self.returncode is None:
            self.returncode = self.final_returncode
        return self.returncode

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminate_calls += 1
        if self.returncode is None:
            self.returncode = -15

    def kill(self):
        self.kill_calls += 1
        if self.returncode is None:
            self.returncode = -9


class WatchDrissionPageTests(unittest.TestCase):
    def test_run_forever_restarts_after_exit_and_terminates_child_on_keyboard_interrupt(self):
        module = load_watchdog_module()
        self.assertIsNotNone(module, "watch_drissionpage.py should exist")

        processes = [
            FakeProcess(returncode=0),
            FakeProcess(interrupt_on_wait=True),
        ]
        launched_commands = []
        sleep_calls = []
        logs = []

        def fake_popen(command, cwd=None):
            launched_commands.append((command, cwd))
            return processes[len(launched_commands) - 1]

        with self.assertRaises(KeyboardInterrupt):
            module.run_forever(
                ["python", "DrissionPage_example.py"],
                cwd=str(ROOT),
                restart_delay=2,
                popen_factory=fake_popen,
                sleep_func=lambda seconds: sleep_calls.append(seconds),
                log_func=lambda message: logs.append(message),
            )

        self.assertEqual(len(launched_commands), 2)
        self.assertEqual(sleep_calls, [2])
        self.assertEqual(processes[1].terminate_calls, 1)

    def test_build_command_uses_current_python_and_forwards_args(self):
        module = load_watchdog_module()
        self.assertIsNotNone(module, "watch_drissionpage.py should exist")

        command = module.build_command(["--count", "1"])

        self.assertEqual(command[0], sys.executable)
        self.assertEqual(Path(command[1]).resolve(), ROOT / "DrissionPage_example.py")
        self.assertEqual(command[2:], ["--count", "1"])


if __name__ == "__main__":
    unittest.main()
