from __future__ import annotations

import os
import re
import subprocess
import sys

from . import procs

TASK_NAME = "Z-GUI"


def task_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--tray"]
    return [sys.executable, "-m", "app", "--tray"]


def exists() -> bool:
    return procs.run(["schtasks.exe", "/Query", "/TN", TASK_NAME], timeout=20).code == 0


def create() -> bool:
    command = subprocess.list2cmdline(task_command())
    result = procs.run(
        [
            "schtasks.exe",
            "/Create",
            "/TN",
            TASK_NAME,
            "/TR",
            command,
            "/SC",
            "ONLOGON",
            "/RL",
            "HIGHEST",
            "/F",
        ],
        timeout=45,
    )
    return result.code == 0


def delete() -> bool:
    return procs.run(["schtasks.exe", "/Delete", "/TN", TASK_NAME, "/F"], timeout=30).code == 0


def xml() -> str:
    return procs.run(["schtasks.exe", "/Query", "/TN", TASK_NAME, "/XML"], timeout=20).text


def configured_command() -> str | None:
    match = re.search(r"<Command>(.*?)</Command>", xml(), re.DOTALL)
    if not match:
        return None
    return match.group(1).strip()


def matches() -> bool:
    configured = configured_command()
    if not configured:
        return False
    expected = task_command()[0]
    return os.path.normcase(os.path.normpath(configured)) == os.path.normcase(
        os.path.normpath(expected)
    )


def sync(enabled: bool) -> bool:
    if not getattr(sys, "frozen", False):
        return not enabled
    if enabled:
        if exists() and matches():
            return True
        if exists():
            delete()
        return create()
    if exists():
        return delete()
    return True
