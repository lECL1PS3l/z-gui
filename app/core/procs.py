from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000


@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str

    @property
    def text(self) -> str:
        return (self.out + "\n" + self.err).strip()


def _decode(raw: bytes) -> str:
    for encoding in ("oem", "utf-8"):
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", "replace")


def run(
    args: list[str],
    timeout: float = 30.0,
    cwd: Path | None = None,
) -> Result:
    try:
        completed = subprocess.run(
            [str(part) for part in args],
            capture_output=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            creationflags=CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return Result(-2, "", "timeout")
    except OSError as exc:
        return Result(-1, "", str(exc))
    return Result(completed.returncode, _decode(completed.stdout), _decode(completed.stderr))


def winws_pids() -> list[int]:
    import psutil

    pids: list[int] = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = (proc.info.get("name") or "").lower()
        except psutil.Error:
            continue
        if name == "winws.exe":
            pids.append(int(proc.info["pid"]))
    return pids


def winws_running() -> bool:
    return bool(winws_pids())


def kill_winws(timeout: float = 8.0) -> int:
    import psutil

    killed = 0
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = (proc.info.get("name") or "").lower()
        except psutil.Error:
            continue
        if name != "winws.exe":
            continue
        try:
            proc.kill()
            proc.wait(timeout=timeout)
            killed += 1
        except psutil.Error:
            pass
    return killed
