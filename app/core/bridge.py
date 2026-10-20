from __future__ import annotations

import asyncio
import importlib
import logging
import os
import socket
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path


class BridgeError(RuntimeError):
    pass


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", int(port)))
        except OSError:
            return False
    return True


def pick_port(preferred: int = 1443, low: int = 1443, high: int = 1450) -> int:
    if not preferred:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])
    if port_free(preferred):
        return int(preferred)
    for candidate in range(low, high + 1):
        if port_free(candidate):
            return candidate
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def tcp_ready(port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def link_for(port: int, secret: str) -> str:
    return f"tg://proxy?server=127.0.0.1&port={int(port)}&secret=dd{secret}"


class Bridge:
    def __init__(self, parent: Path, log_file: Path | None = None) -> None:
        self.parent = Path(parent)
        self.log_file = Path(log_file) if log_file else None
        self.port: int | None = None
        self.secret = ""
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop: asyncio.Event | None = None
        self._started = False
        self._error: str | None = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and self._started)

    def _configure_logging(self) -> None:
        logger = logging.getLogger("tg-mtproto-proxy")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if self.log_file is not None and not getattr(logger, "_zgui_handler", False):
            try:
                self.log_file.parent.mkdir(parents=True, exist_ok=True)
                handler = RotatingFileHandler(
                    self.log_file,
                    maxBytes=5 * 1024 * 1024,
                    backupCount=1,
                    encoding="utf-8",
                )
                handler.setFormatter(
                    logging.Formatter("%(asctime)s %(levelname)-5s %(message)s", datefmt="%H:%M:%S")
                )
                logger.addHandler(handler)
            except OSError:
                pass
            logger._zgui_handler = True
        for name in ("asyncio", "httpx", "httpcore"):
            logging.getLogger(name).setLevel(logging.WARNING)

    def _load(self, port: int, secret: str):
        for key in [key for key in list(sys.modules) if key == "proxy" or key.startswith("proxy.")]:
            sys.modules.pop(key, None)
        parent = str(self.parent)
        if parent in sys.path:
            sys.path.remove(parent)
        sys.path.insert(0, parent)
        importlib.invalidate_caches()
        module = importlib.import_module("proxy.tg_ws_proxy")
        config_module = importlib.import_module("proxy.config")
        config = config_module.proxy_config
        config.host = "127.0.0.1"
        config.port = int(port)
        config.secret = secret
        config.dc_redirects = {2: "149.154.167.220", 4: "149.154.167.220"}
        config.buffer_size = 256 * 1024
        config.pool_size = 4
        config.fallback_cfproxy = True
        config.cfproxy_h2_media = True
        config.disable_secure = False
        config.fake_tls_domain = ""
        config.proxy_protocol = False
        config.force_test_dc = False
        return module

    def _main(self, port: int, secret: str) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._stop = asyncio.Event()
        self._started = True
        try:
            module = self._load(port, secret)
            loop.run_until_complete(module._run(self._stop))
        except BaseException as exc:
            self._error = f"{type(exc).__name__}: {exc}"
        finally:
            self._started = False
            try:
                loop.close()
            except Exception:
                pass

    def start(self, port: int, secret: str, timeout: float = 25.0) -> None:
        if self.running:
            return
        self._error = None
        self._started = False
        self.port = int(port)
        self.secret = secret
        self._configure_logging()
        self._thread = threading.Thread(
            target=self._main, args=(port, secret), name="tg-bridge", daemon=True
        )
        self._thread.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._error:
                raise BridgeError(self._error)
            if self._started and tcp_ready(self.port):
                return
            if not self._thread.is_alive():
                raise BridgeError(self._error or "мост остановился")
            time.sleep(0.1)
        raise BridgeError("мост не отвечает")

    def stop(self, timeout: float = 6.0) -> None:
        loop = self._loop
        stop_event = self._stop
        if loop is not None and stop_event is not None:
            try:
                loop.call_soon_threadsafe(stop_event.set)
            except RuntimeError:
                pass
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
        self._thread = None
        self._loop = None
        self._stop = None
        self._started = False


def smoke(path: str) -> int:
    target = Path(path)
    if (target / "proxy").is_dir():
        parent = target
    elif (target / "tg_ws_proxy.py").exists():
        parent = target.parent
    else:
        return 1
    bridge = Bridge(parent)
    port = pick_port(0)
    secret = os.urandom(16).hex()
    try:
        bridge.start(port, secret, timeout=30)
        return 0 if tcp_ready(port) else 1
    except BridgeError:
        return 1
    finally:
        bridge.stop()
