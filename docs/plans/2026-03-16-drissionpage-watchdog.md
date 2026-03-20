# DrissionPage Watchdog Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a standalone Python watchdog that repeatedly launches `DrissionPage_example.py` and restarts it whenever the child process exits.

**Architecture:** Add a small root-level supervisor script that delegates work to the existing registration script through `subprocess.Popen()`. Keep the core restart loop in a dedicated function so the behavior is easy to test with `unittest` fakes and mocks.

**Tech Stack:** Python standard library (`argparse`, `subprocess`, `time`, `signal`-safe shutdown patterns, `unittest`)

---

### Task 1: Add the regression test

**Files:**
- Create: `tests/test_watch_drissionpage.py`

**Step 1: Write the failing test**

```python
def test_run_forever_restarts_after_exit_and_terminates_on_keyboard_interrupt():
    ...
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_watch_drissionpage.py -v`
Expected: FAIL because `watch_drissionpage` does not exist yet.

**Step 3: Write minimal implementation**

Create the watchdog module with testable helpers and the restart loop.

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_watch_drissionpage.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_watch_drissionpage.py watch_drissionpage.py
git commit -m "feat: add drissionpage watchdog"
```

### Task 2: Add CLI entry behavior

**Files:**
- Modify: `watch_drissionpage.py`
- Modify: `tests/test_watch_drissionpage.py`

**Step 1: Write the failing test**

```python
def test_build_command_uses_current_python_and_forwards_args():
    ...
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_watch_drissionpage.py -v`
Expected: FAIL because command construction or argument forwarding is incomplete.

**Step 3: Write minimal implementation**

Expose a helper that resolves the target script path and builds the command from `sys.executable` plus forwarded arguments.

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_watch_drissionpage.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_watch_drissionpage.py watch_drissionpage.py
git commit -m "test: cover watchdog command building"
```

### Task 3: Verify the final behavior

**Files:**
- Modify: `watch_drissionpage.py`

**Step 1: Run the focused test suite**

Run: `python3 -m unittest tests/test_watch_drissionpage.py -v`
Expected: PASS

**Step 2: Run the watchdog help command**

Run: `python3 watch_drissionpage.py --help`
Expected: exit code `0` and CLI usage text.

**Step 3: Review the diff**

Run: `git diff -- docs/plans/2026-03-16-drissionpage-watchdog-design.md docs/plans/2026-03-16-drissionpage-watchdog.md tests/test_watch_drissionpage.py watch_drissionpage.py`
Expected: only the planned watchdog additions.

**Step 4: Commit**

```bash
git add docs/plans/2026-03-16-drissionpage-watchdog-design.md docs/plans/2026-03-16-drissionpage-watchdog.md tests/test_watch_drissionpage.py watch_drissionpage.py
git commit -m "feat: add standalone watchdog for drissionpage"
```
