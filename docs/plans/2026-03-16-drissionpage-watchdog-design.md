# DrissionPage Watchdog Design

**Date:** 2026-03-16

**Goal:** Add a standalone Python watchdog script that repeatedly launches `DrissionPage_example.py` and automatically restarts it whenever the child process exits for any reason.

## Context

The repository already contains `DrissionPage_example.py`, which has its own internal per-round loop. The user explicitly asked for a separate outer watchdog rather than changing the existing script behavior. That means the new solution should stay decoupled from the registration logic and simply supervise process lifetime.

## Requirements

- The watchdog must be a standalone Python script.
- It must start `DrissionPage_example.py` using the current Python interpreter by default.
- It must restart the child process after any exit, including exit code `0`, non-zero exits, and unexpected failures.
- It should wait briefly before restarting to avoid a tight failure loop.
- `Ctrl+C` should stop the watchdog and attempt to terminate the currently running child process cleanly.

## Approaches Considered

### 1. Standalone `subprocess` watchdog

Run `DrissionPage_example.py` as a child process in an infinite loop, wait for exit, sleep for a short delay, then restart. This is the recommended approach because it is simple, explicit, and does not require changes to the existing business logic.

### 2. Add restart logic inside `DrissionPage_example.py`

Wrap `main()` in another loop in the existing file. This would work technically, but it violates the user's requirement for a separate outer script and mixes supervision with application behavior.

### 3. Shell or batch wrapper

Use `sh` or `bat` to relaunch the script. This is lighter, but the user explicitly requested a Python script, and Python gives better signal handling and cross-platform behavior.

## Chosen Design

Create `watch_drissionpage.py` in the repository root. The script will:

- Resolve `DrissionPage_example.py` relative to its own file location.
- Build a child command from `sys.executable` plus the target script path and any forwarded arguments.
- Launch the child with `subprocess.Popen()`.
- Wait for the child to exit, log the exit code, sleep for a fixed delay, then restart.
- On `KeyboardInterrupt`, terminate the active child and exit the watchdog.

## Error Handling

- If the target script file is missing, the watchdog should fail fast with a clear error.
- If child termination during shutdown hangs, the watchdog should escalate from `terminate()` to `kill()` after a short timeout.
- Restart behavior should not depend on child exit codes.

## Testing Strategy

Use `unittest` with mocks/fakes rather than starting a real browser flow. The core regression test should verify:

- The watchdog launches a second child after the first child exits normally.
- A `KeyboardInterrupt` during a later wait causes the active child to be terminated.
- Command construction uses the current Python interpreter and target script path.
