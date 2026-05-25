# nrs_toolkit

Personal Python utilities for logging, process monitoring, and more.

## Installation

```bash
pip install git+https://github.com/nschaefer1/nrs-toolkit.git
```

## What's included

- **`nrs_toolkit.telemetry`** — structured logging with optional real-time broadcast of log records and process stats over TCP. See [telemetry/README.md](nrs_toolkit/telemetry/README.md) for full docs.
  - `AdvancedLogger` — configurable logger with console + file output and optional TCP listener.
  - `ClientConnection` — connects to a listener and exposes recent logs and stats.

## Quick example

```python
from nrs_toolkit.telemetry import AdvancedLogger
import logging

AdvancedLogger(listener=True, port=9800)

logger = logging.getLogger(__name__)
logger.info("Service started")
```

## Requirements

- Python 3.12+
- `psutil` (installed automatically)

## License

MIT