import logging
logger = logging.getLogger(__name__)

import threading
import time as t
import os
import signal
from datetime import datetime, time

class WindowGuard:
    """
    Background time-window guard.
 
    ***Spawns a daemon thread on instantiation (unless `delay_invoke=True`).***
 
    This class polls the current time at a fixed interval and reports whether the
    process is currently inside a configured (start, end) window. Depending on
    the configured action, it can either simply expose a flag (`report`) or
    send `SIGTERM` to the current process (`terminate`).
 
    The class supports two action modes:
        - `report`: sets `self.fact = True` while in-window, otherwise `False`.
        - `terminate`: sets the flag and also fires `os.kill(os.getpid(), SIGTERM)`.
 
    Accepted `args` and `kwargs`:
        - `window_min` (tuple[int, int], optional): window start as `(hour, minute)`. Defaults to `(2, 0)`.
        - `window_max` (tuple[int, int], optional): window end as `(hour, minute)`. Defaults to `(3, 0)`.
            Windows that cross midnight are supported (e.g. `(22, 0)` to `(2, 0)`).
 
        - `action` (str, optional, `report | terminate`): behavior when in-window. Defaults to `report`.
        - `interval` (int, optional): polling interval in seconds. Must be `>= 5`. Defaults to `30`.
        - `delay_invoke` (bool, optional): if True, the polling thread is not started until `run()` is called. Defaults to False.
 
    Most common configurations:
        - `WindowGuard((2, 0), (3, 0))`: pause-aware utility — report only, caller checks `.fact`.
        - `WindowGuard((2, 0), (2, 30), action="terminate")`: schedule a nightly self-restart.
        - `WindowGuard((22, 0), (2, 0), action="terminate")`: cross-midnight termination window.
 
    Raises `ValueError` if `interval < 5`, `window_min == window_max`, or `action` is not in `{"report", "terminate"}`.
    """

    def __init__(
        self,
        window_min:tuple = (2, 0),      # (hour, min)
        window_max:tuple = (3, 0),      # (hour, min)
        *,
        action:str = "report",          # report | terminate | error
        interval:int = 30,              # seconds
        delay_invoke:bool = False,     
    ):
        
        self.interval = interval
        if self.interval < 5:
            raise ValueError("Interval must be greater than or equal to 5.")
        
        self.start = time(*window_min)
        self.end = time(*window_max)
        if self.start == self.end:
            raise ValueError("Times cannot be equal.")

        self.action = action
        if self.action not in {"report", "terminate"}:
            raise ValueError(rf"Action of '{self.action}' is not allowed. Acceptable values are 'report' or 'terminate'.")
        
        self._fact = False
        if not delay_invoke:
            self.run()

    @property
    def fact(self):
        return self._fact
        
    def run(self):
        threading.Thread(target = self._check_loop, daemon=True).start()

    def _check_loop(self):
        while True:
            self._fact = self._check_time()           
            if self._fact:
                logger.warning(f'WindowGuard Notification | Currently in window, proceeding with action: {self.action}')
                if self.action == 'terminate':
                    os.kill(os.getpid(), signal.SIGTERM)
            t.sleep(self.interval)               

    def _check_time(self):
        now = datetime.now().time()
        if self.start <= self.end:
            return self.start <= now <= self.end
        return now >= self.start or now <= self.end
    


        