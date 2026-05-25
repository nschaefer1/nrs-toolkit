# nrs_toolkit

Personal Python utilities — logging, and more to come.

## Installation

```
pip install git+https://github.com/nschaefer1/nrs-toolkit.git
```

## What's included

- `nrs_toolkit.logging.AdvancedLogger` — configurable logger with file output and optional TCP broadcast listener for live log/stats streaming.

## Usage

```python
from nrs_toolkit.logging import AdvancedLogger

log = AdvancedLogger(listener=True, port=9800)
import logging
logging.info("Service started")
```

## Requirements

- Python 3.11+
- `psutil` (installed automatically)

## License

MIT