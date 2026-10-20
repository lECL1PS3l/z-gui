from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from .locks import FileLock

DEFAULTS: dict[str, Any] = {
    "version": 1,
    "app_version": "",
    "zapret_version": None,
    "zapret_published_at": None,
    "zapret_installed_at": None,
    "proxy_version": None,
    "proxy_published_at": None,
    "strategy": "general.bat",
    "zapret_enabled": False,
    "bridge_enabled": False,
    "game_filter": False,
    "autostart": True,
    "proxy_port": 1443,
    "proxy_secret": "",
    "last_check": None,
    "pending_update": None,
    "results": [],
    "baseline": None,
    "window": None,
}


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = FileLock(self.path.with_name(self.path.name + ".lock"))

    def read(self) -> dict:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = {}
        data = deepcopy(DEFAULTS)
        if isinstance(raw, dict):
            data.update(raw)
        if not data.get("results"):
            data["results"] = []
        if not data.get("proxy_secret"):
            data["proxy_secret"] = os.urandom(16).hex()
        return data

    def write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, self.path)

    def update(self, mutate: Callable[[dict], Any]) -> dict:
        with self._lock:
            data = self.read()
            mutate(data)
            self.write(data)
            return data

    def ensure_secret(self) -> str:
        def mutate(data: dict) -> None:
            if not data.get("proxy_secret"):
                data["proxy_secret"] = os.urandom(16).hex()

        return str(self.update(mutate)["proxy_secret"])

    def set(self, **values: Any) -> dict:
        def mutate(data: dict) -> None:
            data.update(values)

        return self.update(mutate)


def load(path: Path) -> dict:
    return StateStore(path).read()


def atomic_write(path: Path, data: dict) -> None:
    StateStore(path).write(data)
