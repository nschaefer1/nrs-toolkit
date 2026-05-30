import logging
logger = logging.getLogger(__name__)

import sys
import subprocess
import signal
from typing import Iterable

def install_signal_cleanup(
    processes: Iterable[subprocess.Popen] = (),
    *,
    timeout: float = 5.0,
    exit_code: int = 0,
):
    """
    Install SIGTERM/SIGINT handlers that terminate the given subprocesses cleanly before exiting Python.
    
    Usage:
        - proc = subprocess.Popen([...])
        - install_signal_cleanup([proc])
        
    **Now if anything sends SIGTERM (e.g., WindowGuard, NSSM, Ctrl+C), `proc` is terminated before Python exits.**
      
    - `processes` (Iterable[subprocess]): an iterable of Popen objects to clean up.  
    - `timeout` (float, optional): seconds to wait for graceful terminate before forcing kill.  
    - `exit_code` (int, optional): process exit code to use after cleanup.
    """
    procs = list(processes)

    def handler(signum, frame):
        logger.warning(f'Received signal {signum}, shutting down {len(procs)} subprocess(es)')
        for proc in procs:
            if proc.poll() is None:     # still running
                try:
                    proc.terminate()
                    proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    logger.error(f'PID {proc.pid} did not terminate, killing...')
                    proc.kill()
                except Exception as e:
                    logger.error(f'Cleanup error for PID {proc.pid}: {e}')
        sys.exit(exit_code)
    
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)