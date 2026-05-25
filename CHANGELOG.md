# Change Log

---

### v0.0.1 → v0.0.2

#### Features

- New `ClientConnection` class in `nrs_toolkit/telemetry` (7f0a0ba).  
    This class connects to `AdvancedLogger` listening ports via `socket.bind(...)`. Multiple clients can connect to a single port.  
    See `nrs_toolkit/telemetry/README.md`.
- `AdvancedLogger` errors loudly with a `RuntimeError` if a `socket.bind(...)` is attempted on a port with a preexisting connection (1cfcc16).  
    This prevents silent errors in the daemon threads spawned by `AdvancedLogger`.
- Import capabilities are expanded. `v0.0.1` only offered direct class/function importing (42852e8).  
    **New**: `import nrs_toolkit as nrs`.  
    Followed by: `nrs.telementry.ClientConnection`.

#### Restructure/Rename

Modules were renamed and restructured, including the removal of the `src/` directory (afb6f67) and the naming change from `logging` to `telemetry` to avoid conflicting with the standard Python `logging` module (f53f762).

#### Misc

- Module comment and docstrings were improved (9bdd47e).
- Documentation updates (e.g., README, CHANGELOG)

---