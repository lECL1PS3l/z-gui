from __future__ import annotations

import subprocess
import sys

from . import paths, winapi


def self_command(*args: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, "-m", "app", *args]


def spawn(*args: str, cwd: str | None = None) -> None:
    target = cwd
    if target is None and not getattr(sys, "frozen", False):
        target = str(paths.resource_dir())
    winapi.spawn_detached(self_command(*args), cwd=target)
