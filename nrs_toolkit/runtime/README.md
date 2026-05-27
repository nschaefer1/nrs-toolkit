# nrs_toolkit.runtime

Process lifecycle utilities for long-running scripts: scheduled-window self-termination and subprocess cleanup on shutdown signals.

This module collects small tools for managing the *runtime* of a Python script — when it should stop, what it should clean up when it does, and how to compose those concerns with the rest of your code.

## When to use this

- **You need a script to die during a maintenance window.** Use `WindowGuard` to trigger a termination (or just a flag) every day between configurable times.
- **Your script spawns subprocesses and needs to clean them up.** Use `install_signal_cleanup` so that any `SIGTERM` or `SIGINT` aimed at Python also terminates the children before exiting.
- **You're wrapping a script as a Windows service** (via NSSM or similar) and need predictable shutdown behavior on restart, scheduled tasks, or daily reboots.

## Components

| Component | Role |
|---|---|
| `WindowGuard` | Background thread that polls the current time on an interval. Sets a flag (and optionally fires `SIGTERM`) when inside a configured time window. |
| `install_signal_cleanup` | Registers `SIGTERM` and `SIGINT` handlers that terminate a given list of subprocesses before exiting Python. |

The two are independent. They're often used together because `WindowGuard`'s `terminate` action fires `SIGTERM` at the current process — and `install_signal_cleanup` is exactly what catches that signal and shuts subprocesses down cleanly. But each works on its own.

## Architecture

```text
Main thread             WindowGuard thread          OS signals
    │                         │                          │
    │                    (interval poll)                 │
    │                         │                          │
    │                    in window? ──── yes ──────→ SIGTERM
    │                                                    │
    ↓                                                    ↓
install_signal_cleanup ─────────── catches ──────── handler runs
    │                                                    │
    │                                             terminate procs
    │                                              sys.exit(code)
```

`WindowGuard` and `install_signal_cleanup` never reference each other. The OS signal mechanism is the bridge between them, which is what keeps them independently useful.

---

## `WindowGuard` — quick start

### Report mode (set a flag, take no action)

```python
from nrs_toolkit.runtime import WindowGuard
import time

guard = WindowGuard(
    window_min=(2, 0),     # 2:00 AM
    window_max=(3, 0),     # 3:00 AM
    action="report",
    interval=30,
)

while True:
    if guard.fact:
        print("In window — pausing work")
    else:
        do_work()
    time.sleep(1)
```

Useful when the calling script wants to handle the window itself — pause work, skip a job, log a marker, etc.

### Terminate mode (kill the process)

```python
from nrs_toolkit.runtime import WindowGuard

WindowGuard(
    window_min=(2, 0),
    window_max=(3, 0),
    action="terminate",
)

# Script proceeds normally. When the window hits, SIGTERM is sent
# to the current process. Default Python behavior is to die.
main_loop()
```

Combine with `install_signal_cleanup` (below) if subprocesses need to die too.

---

## `install_signal_cleanup` — quick start

```python
import subprocess
from nrs_toolkit.runtime import install_signal_cleanup

proc = subprocess.Popen(["cloudflared", "tunnel", "run", "mytunnel"])
install_signal_cleanup([proc])

# Now any SIGTERM or SIGINT (Ctrl+C, NSSM stop, WindowGuard terminate)
# will terminate `proc` before Python exits.
proc.wait()
```

Multiple subprocesses are supported — pass the full list:

```python
install_signal_cleanup([proc1, proc2, proc3])
```

---

## `WindowGuard` reference

**Background thread.** Spawning a `WindowGuard` immediately starts a daemon thread that polls the current time on the configured interval. The thread dies with the main process.

### Constructor

```python
WindowGuard(
    window_min=(2, 0),      # (hour, min)
    window_max=(3, 0),      # (hour, min)
    *,
    action="report",
    interval=30,
    delay_invoke=False,
)
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `window_min` | `tuple[int, int]` | `(2, 0)` | Window start as `(hour, minute)`. |
| `window_max` | `tuple[int, int]` | `(3, 0)` | Window end as `(hour, minute)`. Windows that cross midnight are supported (e.g. `(22, 0)` to `(2, 0)`). |
| `action` | `str` | `"report"` | What to do when in-window. `"report"` sets `.fact = True`. `"terminate"` additionally fires `SIGTERM` to the current process. |
| `interval` | `int` | `30` | Polling interval in seconds. Must be at least 5. |
| `delay_invoke` | `bool` | `False` | If `True`, the polling thread is not started until you call `.run()` explicitly. Useful for testing or deferred startup. |

Raises `ValueError` if `interval < 5`, `window_min == window_max`, or `action` is not in `{"report", "terminate"}`.

### Attributes

| Attribute | Type | Description |
|---|---|---|
| `fact` | `bool` | `True` if the last check found the current time inside the window. Read-only via property. |
| `start` | `datetime.time` | Parsed window start. |
| `end` | `datetime.time` | Parsed window end. |
| `action` | `str` | Configured action. |
| `interval` | `int` | Polling interval in seconds. |

### Methods

- **`run()`** — Start the polling thread. Called automatically from `__init__` unless `delay_invoke=True`.

### Common configurations

```python
# Pause work during nightly maintenance
WindowGuard((2, 0), (3, 0), action="report")

# Auto-restart at 2 AM (relies on NSSM or supervisor to bring it back up)
WindowGuard((2, 0), (2, 30), action="terminate")

# Cross-midnight window (10 PM to 2 AM)
WindowGuard((22, 0), (2, 0), action="terminate")
```

---

## `install_signal_cleanup` reference

```python
install_signal_cleanup(
    processes=(),
    *,
    timeout=5.0,
    exit_code=0,
)
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `processes` | `Iterable[subprocess.Popen]` | `()` | Subprocesses to terminate when a signal arrives. Snapshotted into a list at registration time. |
| `timeout` | `float` | `5.0` | Seconds to wait for graceful `terminate()` before escalating to `kill()`. |
| `exit_code` | `int` | `0` | Exit code Python uses after cleanup. |

### Behavior

Registers a handler for `SIGTERM` and `SIGINT`. When either fires:

1. Logs the received signal and number of processes being shut down.
2. For each process still running (`poll() is None`):
   - Calls `terminate()`, then `wait(timeout=...)`.
   - If the timeout expires, escalates to `kill()`.
   - Catches and logs any other cleanup exceptions, then moves on.
3. Calls `sys.exit(exit_code)`.

### Common configurations

```python
# Default — clean shutdown of one child
install_signal_cleanup([proc])

# Multiple children
install_signal_cleanup([db_proc, web_proc, worker_proc])

# Longer grace period for a slow-to-shutdown child
install_signal_cleanup([proc], timeout=15.0)

# Signal an error exit so NSSM doesn't treat it as a normal shutdown
install_signal_cleanup([proc], exit_code=1)
```

---

## Coupling opportunities

Although the two tools are independent, they compose naturally for daemons that need scheduled restarts:

```python
import subprocess
from nrs_toolkit.runtime import WindowGuard, install_signal_cleanup

# Spawn the workload
proc = subprocess.Popen(["cloudflared", "tunnel", "run", "mytunnel"])

# Wire up cleanup before anything can trigger it
install_signal_cleanup([proc])

# Schedule the daily restart window
WindowGuard(
    window_min=(2, 0),
    window_max=(2, 30),
    action="terminate",
)

# Block until cloudflared exits (or a signal kills us)
proc.wait()
```

**Order matters.** Register `install_signal_cleanup` *before* starting the `WindowGuard`. If the guard fires before the handler is installed, Python uses its default behavior (die immediately, no subprocess cleanup).

For Windows services, pair this with NSSM's `AppExit` setting set to `Restart` — the script exits cleanly during its window, NSSM restarts it, and the cycle continues automatically.

---

## Notes & gotchas

- **Signal handlers must be installed from the main thread.** Don't call `install_signal_cleanup` from inside a worker thread. Python will raise `ValueError`.
- **Daemon thread caveat.** `WindowGuard`'s polling thread is a daemon, so it dies silently when the main process exits. This is intentional — the guard should never keep a process alive on its own.
- **`os.kill` on Windows.** `WindowGuard` uses `os.kill(os.getpid(), signal.SIGTERM)` to fire its termination. This works on Windows via Python's emulation layer, but only catches handlers installed in the same Python process. It does *not* send a signal to the OS the way it would on Linux.
- **`install_signal_cleanup` replaces existing handlers.** If another part of your code has registered a `SIGTERM` handler, this overwrites it. Install once, near program start.
- **`proc.poll() is None` is checked at handler time.** If a subprocess died on its own before the handler fires, it's skipped — no double-kill errors.
- **Cross-thread exception propagation.** `WindowGuard` cannot raise an exception that propagates to your main thread. If you need cross-thread coordination beyond `SIGTERM`, poll `guard.fact` from the main thread and raise yourself.