from __future__ import annotations

import os
import threading
import time
from pathlib import Path

try:
    import msvcrt
except ImportError:
    msvcrt = None


class FileLock:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._handle = None
        self._guard = threading.Lock()
        self._local = threading.local()

    def _depth(self) -> int:
        return int(getattr(self._local, "depth", 0))

    def acquire(self, timeout: float = 30.0) -> bool:
        if self._depth() > 0:
            self._local.depth = self._depth() + 1
            return True
        deadline = time.monotonic() + max(timeout, 0.0)
        while True:
            acquired = False
            with self._guard:
                if self._handle is None:
                    handle = None
                    try:
                        self.path.parent.mkdir(parents=True, exist_ok=True)
                        handle = open(self.path, "a+b")
                    except OSError:
                        handle = None
                    if handle is not None:
                        try:
                            handle.seek(0)
                            if msvcrt is not None:
                                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                            self._handle = handle
                            acquired = True
                        except OSError:
                            handle.close()
                            handle = None
            if acquired:
                self._local.depth = 1
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)

    def release(self) -> None:
        depth = self._depth()
        if depth <= 0:
            return
        if depth > 1:
            self._local.depth = depth - 1
            return
        self._local.depth = 0
        with self._guard:
            handle = self._handle
            self._handle = None
            if handle is None:
                return
            try:
                handle.seek(0)
                if msvcrt is not None:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            finally:
                handle.close()

    def __enter__(self) -> "FileLock":
        if not self.acquire():
            raise TimeoutError(f"lock busy: {self.path}")
        return self

    def __exit__(self, *args) -> None:
        self.release()


class OpsLock(FileLock):
    def try_enter(self) -> bool:
        return self.acquire(timeout=0)


_locks: dict[str, FileLock] = {}
_locks_guard = threading.Lock()


def ops_lock(path: Path) -> FileLock:
    key = os.path.normcase(os.path.abspath(str(path)))
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = FileLock(path)
            _locks[key] = lock
        return lock
