from __future__ import annotations

from . import procs


def sync_state(store, zapret) -> dict:
    if not zapret.lock.acquire(timeout=0):
        return store.read()
    try:
        status = zapret.status()
        if status == "missing" and procs.winws_running():
            procs.kill_winws()
        enabled = status == "running" and procs.winws_running()
        data = store.read()
        if bool(data.get("zapret_enabled")) != enabled:
            return store.set(zapret_enabled=enabled)
        return data
    finally:
        zapret.lock.release()
