# nrs_toolkit.telemetry

Structured logging with optional real-time broadcasting of log records and process statistics over TCP.

This module combines standard Python logging with a lightweight publish/subscribe model: one process (the **listener**) configures logging and optionally broadcasts records over a socket; one or more **clients** connect to that socket to observe logs and process metrics in real time.

## When to use this

- **You want normal Python logging.** Use `AdvancedLogger` for sensible defaults (console + optional file output) without writing boilerplate.
- **You want to monitor a running process.** Enable the listener and connect a `ClientConnection` from another process to receive live log records and CPU/RAM stats.
- **You're building a dashboard or dev tool.** The client retains bounded message history, so you can render recent logs and a stats timeline without managing buffers yourself.

## Components

| Component | Role |
|---|---|
| `AdvancedLogger` | Configures Python's `logging` module. Adds console output, optional file output, and an optional TCP listener that broadcasts to connected clients. |
| `ClientConnection` | Connects to a listener, reads newline-delimited JSON in a background thread, and exposes recent log and stat messages via bounded queues. |
| `BroadcastHandler` | Internal `logging.Handler` that pushes every log record to all connected clients. Attached automatically when `listener=True`. |

## Architecture

```text
┌───────────────────────────────────────┐
│  Listener process                     │
│                                       │
│  AdvancedLogger(listener=True)        │
│    ├── console (StreamHandler)        │
│    ├── file    (FileHandler)          │   ← if dev=False
│    └── socket  (BroadcastHandler) ────┼──┐
│                                       │  │
│  Stats daemon ────────────────────────┼──┤   newline-delimited JSON
└───────────────────────────────────────┘  │   over TCP
                                           ▼
                          ┌──────────────────────────────────┐
                          │  Client process(es)              │
                          │                                  │
                          │  ClientConnection(port)          │
                          │    ├── .logs           (deque)   │
                          │    ├── .stats          (deque)   │
                          │    └── .latest_stats   (dict)    │
                          └──────────────────────────────────┘
```

Only one listener may bind a given host/port. Multiple clients may connect to the same listener.

## Message format

All messages are JSON objects followed by a `\n`. Three types exist:

```json
{"type": "conn", "msg": "success"}
{"type": "log",   "ts": "2026-05-25T14:32:01", "level": "INFO", "msg": "..."}
{"type": "stats", "ts": "2026-05-25T14:32:01", "cpu": 4.2, "ram_mb": 187.3}
```

- `conn` — sent once on client connection as a handshake.
- `log` — emitted for every log record at or above the configured level.
- `stats` — emitted every 5 seconds by the listener's stats daemon.

---

## Quick start

### Listener (process A)

```python
from nrs_toolkit.telemetry import AdvancedLogger
import logging
import time

# Configure logging + open a listener on 127.0.0.1:9999
AdvancedLogger(dev=True, listener=True, port=9999)

logger = logging.getLogger(__name__)

while True:
    logger.info("heartbeat")
    time.sleep(2.5)
```

`dev=True` skips file output, which is useful while developing. `listener=True` opens the TCP socket and starts the stats daemon.

### Client (process B)

```python
from nrs_toolkit.telemetry import ClientConnection
import time

conn = ClientConnection(9999)

while True:
    if conn.status == "connected":
        print(conn.latest_stats)
        time.sleep(2.5)
    else:
        if not conn.connect():
            print("Connection failed, retrying in 5s...")
            time.sleep(5)
```

The client retries on its own — start order doesn't matter, as long as the listener comes up eventually.

---

## `AdvancedLogger` reference

**Singleton.** Configuration is captured on first instantiation and ignored on subsequent calls. This is intentional: logging should be configured once per process.

### Keyword arguments

| Argument | Type | Default | Description |
|---|---|---|---|
| `level` | `int` | `logging.INFO` | Logging threshold. Auto-set to `DEBUG` if `--debug` is in `sys.argv`. |
| `dev` | `bool` | `False` | If `True`, skips file output (console + listener only). |
| `log_dir` | `str` | `"logs"` | Directory for log files. Created if missing. |
| `log_file` | `str` | `"{timestamp}_{suffix}.log"` | Override the auto-generated filename. |
| `suffix` | `str` | `"run"` | Suffix used in the auto-generated filename. |
| `mode` | `str` | `"a"` | File open mode: `"a"` (append) or `"w"` (overwrite). |
| `listener` | `bool` | `False` | If `True`, opens a TCP listener and starts the stats daemon. |
| `host` | `str` | `"127.0.0.1"` | Bind address for the listener. |
| `port` | `int` | `9999` | Bind port for the listener. Raises `RuntimeError` if already in use. |

### Common configurations

```python
# Early development: console only
AdvancedLogger(dev=True)

# Late development: console + live broadcast, no file noise
AdvancedLogger(dev=True, listener=True)

# Production: file + broadcast on a non-default port
AdvancedLogger(listener=True, port=9800)
```

---

## `ClientConnection` reference

### Constructor

```python
ClientConnection(
    port,                  # required
    *,
    host="127.0.0.1",
    log_limit=500,
    stats_limit=360,
    connect_timeout=2.0,
    recv_size=4096,
)
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `port` | `int` | — | Listener port (required). |
| `host` | `str` | `"127.0.0.1"` | Listener host. |
| `log_limit` | `int` | `500` | Max retained log records. Older records are dropped. |
| `stats_limit` | `int` | `360` | Max retained stat records (~30 min at 5s intervals). |
| `connect_timeout` | `float` | `2.0` | Socket connect timeout in seconds. |
| `recv_size` | `int` | `4096` | Bytes per `recv()` call. |

### Attributes

| Attribute | Type | Description |
|---|---|---|
| `status` | `str` | `"disconnected"`, `"connected"`, or `"error"`. |
| `error` | `str \| None` | Last connection error, if any. |
| `pid` | `int \| None` | PID of the listener process (looked up via `psutil`). |
| `logs` | `deque` | Recent `log` messages, newest at the right. |
| `stats` | `deque` | Recent `stats` messages, newest at the right. |
| `latest_stats` | `dict \| None` | The most recent `stats` message, for cheap access. |

### Methods

- **`connect() -> bool`** — Open the socket and start the reader thread. Returns `True` on success, `False` on failure (check `.error`).
- **`disconnect()`** — Stop the reader thread and close the socket.
- **`clear_logs()`** — Empty the `logs` deque without disconnecting.

---

## Notes & gotchas

- **One listener per port.** Starting a second `AdvancedLogger` with `listener=True` on a port already in use raises `RuntimeError`.
- **Singleton behavior.** The second call to `AdvancedLogger(...)` returns the existing instance and ignores its arguments. Configure once at startup.
- **Thread safety.** The client's reader runs in a daemon thread. Reading `conn.logs` / `conn.stats` from the main thread is safe for inspection but treat them as snapshots — they can mutate between reads.
- **Bounded history.** Both `logs` and `stats` are `deque`s with `maxlen`. Old messages silently drop; persist them yourself if you need full history.
- **Localhost by default.** The listener binds `127.0.0.1`. Change `host` only if you understand the security implications of exposing log streams over the network.