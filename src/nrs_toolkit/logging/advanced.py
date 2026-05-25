import logging
import os
import sys
import time
import threading
import json
import psutil
import socket

from datetime import datetime, timezone
from pathlib import Path

_clients = []
_client_lock = threading.Lock()

def broadcast(payload):
    """
    Send a payload to all listening clients.
    Payloads generally include a `dict` with variables `type`, `ts`, and `msg`; fields vary by message type.
    Recommended `ts` strftime is `"%Y-%m-%dT%H:%M:%S"`.
    """
    with _client_lock:
        dead = []
        for c in _clients:
            try:
                line = (json.dumps(payload) + '\n').encode()
                c.sendall(line)
            except OSError:
                dead.append(c)
        for c in dead:
            _clients.remove(c)
            try:
                c.close()
            except OSError:
                pass

class AdvancedLogger():
    """
    Advanced logger class.
    
    ***Configuration is locked after first instantiation.***

    This class has three logging mechanisms available:     
        - Console logging (StreamHandler): default and always present.  
        - File logging (FileHandler): triggered in production mode.  
        - Listener logging (BroadcastHandler): broadcasts log messages to a port, required explicit enabling.  

    Accepted `kwargs`:  
        - `level` (logging.LEVEL, optional): defaults to `logging.INFO`. Invoking the script with `--debug` defaults to `logging.DEBUG`.  
        
        - `dev` (bool, optional): defaults to False. When True, FileHandler is disabled.
        - `log_dir` (str, optional): defaults to `logs/`. Sets drop directory of the log files.   
        - `log_file` (str, optional): defaults to `{timestamp}_{suffix}.log`  
        - `suffix` (str, optional): suffix in `log_file`, defaults to `run`. 
        - `mode` (str, optional, `a | w`): append `a` or write `w` mode, defaults to `a`.

        - `listener` (bool, optional): triggers the BroadcastHandler logging mechanism, defaults to False.
        - `host` (str, optional): host IP, defaults to `127.0.0.1`.
        - `port` (int, optional): TCP listening port, defaults to `9999`.

    Most common `kwarg` combinations:
        - `dev = True`: disables the log file creation and useful in early development.
        - `dev = True, listener = True`: disables log file creation, opens a listener on the `localhost:9999`. Useful in late-stage development.
        - `listener = True, port = 9800`: creates a log file, opens a listener on `localhost:9800`. Useful in production stages.

    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            
            # Logging level, allows debug mode
            cls._level = kwargs.get('level', None)

            # Logging directory & file & suffix, only used in dev mode
            cls._dev = kwargs.get('dev', False)
            cls._log_dir = kwargs.get('log_dir', 'logs')    # default to the root and create a directory of logs/
            cls._log_file = kwargs.get('log_file', None)
            cls._suffix = kwargs.get('suffix', 'run')
            cls._mode = kwargs.get('mode', 'a')

            # Check broadcasting duty & port assignment
            cls._listener = kwargs.get('listener', False)
            cls._host = kwargs.get('host', "127.0.0.1")
            cls._port = kwargs.get('port', 9999)

            # Start the logger
            cls._instance.init_logger()  

        return cls._instance
    
    def __init__(self, *args, **kwargs):
        super().__init__()

    def init_logger(self):

        self._resolve_level()

        logging.basicConfig(
            level = self._level,
            format = "%(asctime)s [%(levelname)s] %(message)s",
        )
        logger = logging.getLogger(__name__)
        
        self._resolve_log_file(logger)    # adds a FileHandler if requested
    
        if self._listener:
            logging.getLogger().addHandler(BroadcastHandler())
            self._start_listener(logger)

    
    def _resolve_level(self):
        """
        A logging level is *required*.
        If not provided, will default to `logging.INFO`.
        During invocation, utilizing the `--debug` argument will default to `logging.DEBUG`.
        """
        if self._level is None:
            self._level = logging.DEBUG if '--debug' in sys.argv else logging.INFO
    
    def _resolve_log_file(self, logger):
        """
        A logging file is intended to be used post development.
        During first class instantiation, the `dev = False` kwarg is required for a log file to generate.
        If `dev = True` or not provided, a log file will not be generated.
        """
        if self._dev:                       # if we are not in dev mode, we want to log to a file
            return
        
        if not self._log_file:              # need to set up a log file if they don't provide it
            timestamp = datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')
            self._log_file = f"{timestamp}_{self._suffix}.log"
        if self._log_dir:                   # ensure the log directory is set or exists
            Path(self._log_dir).mkdir(parents=True, exist_ok=True)
            self._log_file = Path(self._log_dir) / Path(self._log_file)
        
        logging.getLogger().addHandler(logging.FileHandler(self._log_file, mode=self._mode))
        logger.info('Log file resolved...')

    def _start_listener(self, logger):
        """
        Starts listener. 
        Creates two additional daemon threads to accept clients and broadcast stats to clients.
        """
        srv = self._grab_port()
        threading.Thread(target = self._accept_loop, args= (logger, srv), daemon=True).start()
        threading.Thread(target = self._stats_loop, args= (logger,), daemon=True).start()
        logger.info(f'Listener ready on {self._host}:{self._port}...')

    def _accept_loop(self, logger, srv):
        """
        Accepts clients and reports a `conn: success` message back to the client.
        """
        srv.listen()
        
        while True:
            conn, addr = srv.accept()
            logger.info(f'Client connected from {addr}...')

            try:
                line = (json.dumps({"type": "conn","msg": "success"}) + '\n').encode()
                conn.sendall(line)
            except OSError:
                conn.close()
                continue
                
            _clients.append(conn)

    def _stats_loop(self, logger, interval=5.0):
        """
        Collects process statistics and broadcasts to clients at an `interval`.
        """
        proc = psutil.Process(os.getpid())
        proc.cpu_percent(interval=None)
        logger.info(f'Stats collection daemon started...')

        while True:
            payload = {
                "type":"stats",
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "cpu": proc.cpu_percent(interval=None),
                "ram_mb": round(proc.memory_info().rss / 1024 / 1024, 1),
            }
            broadcast(payload)
            time.sleep(interval)

    def _grab_port(self):
        """
        Bind to the port.
        If the port is already bound by another process, a `RuntimeError` will be raised.
        """
        srv = socket.socket()
        try:
            srv.bind((self._host, self._port))
        except OSError as e:
            raise RuntimeError(
                f"AdvancedLogger listener cannot start on {self._host}:{self._port}. Another process is already bound to that port."
            ) from e
        return srv

    
class BroadcastHandler(logging.Handler):

    def emit(self, record):
        payload = {
            "type": "log",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        broadcast(payload)
    
    