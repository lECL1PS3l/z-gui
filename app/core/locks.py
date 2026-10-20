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
        self._thread_lock = threading.RLock()
        self._depth = 0

    def acquire(self, timeout: float = 30.0) -> bool:
        self._thread_lock.acquire()
        if self._depth > 0:
            self._depth += 1
            self._thread_lock.release()
            return True
        deadline = time.monotonic() + max(timeout, 0.0)
        while True:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                handle = open(self.path, "a+b")
            except OSError:
                self._thread_lock.release()
                return False
            try:
                handle.seek(0)
                if msvcrt is None:
                    self._handle = handle
                    self._depth = 1
                    self._thread_lock.release()
                    return True
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                self._handle = handle
                self._depth = 1
                self._thread_lock.release()
                return True
            except OSError:
                handle.close()
                if time.monotonic() >= deadline:
                    self._thread_lock.release()
                    return False
                time.sleep(0.05)

    def release(self) -> None:
        self._thread_lock.acquire()
        try:
            self._depth -= 1
            if self._depth > 0 or self._handle is None:
                return
            handle = self._handle
            self._handle = None
            try:
                handle.seek(0)
                if msvcrt is not None:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            finally:
                handle.close()
        finally:
            self._thread_lock.release()

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
    key = os.path.abspath(str(path))
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = FileLock(path)
            _locks[key] = lock
        return lock
