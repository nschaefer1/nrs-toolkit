# nrs_toolkit

Personal Python utilities for logging, process monitoring, runtime helpers, and more.

## Installation

```bash
pip install git+https://github.com/nschaefer1/nrs-toolkit.git
```

## What's included

- **`nrs_toolkit.telemetry`** — structured logging with optional real-time broadcast of log records and process stats over TCP. See [telemetry/README.md](nrs_toolkit/telemetry/README.md) for full docs.
  - `AdvancedLogger` — configurable logger with console + file output and optional TCP listener.
  - `ClientConnection` — connects to a listener and exposes recent logs and stats.
- **`nrs_toolkit.runtime`** — runtime assistants and controllers. See [runtime/README.md](nrs_toolkit/runtime/README.md) for full docs.
  - `WindowGuard` — configurable time window monitor to either log or terminate the main process if the system time is within the window.
  - `install_signal_cleanup` — function to terminate/kill subprocesses if the main process receives a `SIGTERM` or `SIGINT`.

## Requirements

- Python 3.12+
- `psutil` (installed automatically)

## License

MIT