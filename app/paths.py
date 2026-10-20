from __future__ import annotations

import os
import sys
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("ZGUI_DATA_DIR")
    if override:
        return Path(override)
    base = os.environ.get("ProgramData") or r"C:\ProgramData"
    return Path(base) / "Z-GUI"


def resource_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def zapret_dir() -> Path:
    return data_dir() / "zapret"


def payload_dir() -> Path:
    return data_dir() / "payload"


def proxy_parent() -> Path:
    return payload_dir()


def logs_dir() -> Path:
    return data_dir() / "logs"


def temp_dir() -> Path:
    return data_dir() / "temp"


def state_path() -> Path:
    return data_dir() / "state.json"


def ipc_path() -> Path:
    return data_dir() / "ipc.json"


def ops_lock_path() -> Path:
    return data_dir() / "ops.lock"


def window_state_path() -> Path:
    return data_dir() / "window.json"


def window_lock_path() -> Path:
    return data_dir() / "window.lock"


def bundled_payload_dir() -> Path:
    return resource_dir() / "payload"


def qml_dir() -> Path:
    return resource_dir() / "app" / "ui" / "qml"


def icon_path() -> Path:
    return resource_dir() / "assets" / "app.ico"


def ensure_dirs() -> None:
    for path in (data_dir(), zapret_dir(), payload_dir(), logs_dir(), temp_dir()):
        path.mkdir(parents=True, exist_ok=True)
