from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from . import paths

_ready = False


def _setup() -> None:
    global _ready
    if _ready:
        return
    root = logging.getLogger("z-gui")
    root.setLevel(logging.INFO)
    root.propagate = False
    try:
        target = paths.logs_dir() / "app.log"
        target.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            target, maxBytes=5 * 1024 * 1024, backupCount=1, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        root.addHandler(handler)
    except OSError:
        root.addHandler(logging.NullHandler())
    for noisy in ("httpx", "httpcore", "asyncio", "urllib3", "h2"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _ready = True


def get_logger(name: str = "z-gui") -> logging.Logger:
    _setup()
    return logging.getLogger(name)
