import logging
logger = logging.getLogger(__name__)

import threading
import time as t
import os
import signal
from datetime import datetime, time

class WindowGuard:

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
    


        