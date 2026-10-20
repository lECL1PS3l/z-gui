from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import __version__, command, ipc, paths, winapi
from .core import autostart, bootstrap, diagnostics, reconcile, updater, versions
from .core import bridge as bridge_mod
from .core.state import StateStore
from .core.zapret import Zapret, ZapretError
from .logs import get_logger

MUTEX_NAME = "Local\\Z-GUI-Tray"
log = get_logger("z-gui.tray")


class TrayApp:
    def __init__(self) -> None:
        self.store = StateStore(paths.state_path())
        self.zapret = Zapret(store=self.store)
        self.bridge = bridge_mod.Bridge(
            paths.proxy_parent(), paths.logs_dir() / "proxy.log"
        )
        self.server: ipc.Server | None = None
        self.icon = None
        self._handle = None
        self._stop = threading.Event()

    def run(self) -> int:
        self._handle = winapi.single_instance(MUTEX_NAME)
        if self._handle is None:
            return 0
        paths.ensure_dirs()
        data = bootstrap.ensure_ready()
        reconcile.sync_state(self.store, self.zapret)
        autostart.sync(bool(data.get("autostart")))
        if data.get("bridge_enabled"):
            try:
                self.start_bridge()
            except Exception:
                log.warning("мост не запустился")
        self.server = ipc.Server(
            paths.ipc_path(),
            {
                "ping": lambda args: {"ok": True, "pid": os.getpid()},
                "show": lambda args: self._async(self.show_window),
                "bridge.start": lambda args: self._bridge_start(),
                "bridge.stop": lambda args: self._bridge_stop(),
                "state": lambda args: self._state(),
                "quit": lambda args: self._async(self.quit),
            },
        )
        self.server.start()
        threading.Thread(target=self._scheduler, name="zgui-scheduler", daemon=True).start()
        self._run_icon()
        self.shutdown()
        return 0

    def _async(self, function) -> dict:
        threading.Thread(target=function, daemon=True).start()
        return {"ok": True}

    def show_window(self) -> None:
        handle = winapi.find_window("Z-GUI")
        if handle:
            winapi.show_window(handle)
            return
        command.spawn("--window")

    def quit(self) -> None:
        self._stop.set()
        if self.icon is not None:
            self.icon.stop()

    def _bridge_start(self) -> dict:
        try:
            self.start_bridge()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        secret = self.store.read().get("proxy_secret") or ""
        return {
            "ok": True,
            "port": self.bridge.port,
            "link": bridge_mod.link_for(int(self.bridge.port or 0), secret),
        }

    def _bridge_stop(self) -> dict:
        self.bridge.stop()
        self.store.set(bridge_enabled=False)
        return {"ok": True}

    def start_bridge(self) -> None:
        if self.bridge.running:
            return
        data = self.store.read()
        port = bridge_mod.pick_port(int(data.get("proxy_port") or 1443))
        secret = self.store.ensure_secret()
        self.bridge.start(port, secret)
        self.store.set(bridge_enabled=True, proxy_port=port)

    def _state(self) -> dict:
        data = self.store.read()
        return {
            "ok": True,
            "bridge": bool(self.bridge.running),
            "port": self.bridge.port or data.get("proxy_port"),
            "zapret": self.zapret.status() == "running",
            "enabled": bool(data.get("zapret_enabled")),
        }

    def _scheduler(self) -> None:
        while not self._stop.is_set():
            try:
                self._maybe_check()
            except Exception as exc:
                log.warning("проверка обновлений: %s", exc)
            self._stop.wait(600)

    def _maybe_check(self) -> None:
        data = self.store.read()
        if data.get("pending_update"):
            return
        last = versions.parse_date(data.get("last_check"))
        now = datetime.now(timezone.utc)
        if last is not None and now - last < timedelta(hours=72):
            return
        offer = updater.check(data)
        self.store.set(last_check=now.replace(microsecond=0).isoformat(), pending_update=offer)
        log.info("проверка обновлений: %s", offer.get("label") if offer else "обновлений нет")
        if offer:
            self._notify(offer)

    def _notify(self, offer: dict) -> None:
        if self.icon is None:
            return
        try:
            self.icon.notify(f"Доступно обновление {offer.get('label', '')}".strip(), "Z-GUI")
        except Exception:
            pass

    def _icon_image(self):
        from PIL import Image

        target = paths.icon_path()
        if target.exists():
            try:
                return Image.open(target)
            except OSError:
                pass
        return Image.new("RGBA", (64, 64), "#3399FF")

    def _run_icon(self) -> None:
        import pystray

        menu = pystray.Menu(
            pystray.MenuItem(
                "Показать окно",
                lambda icon, item: self._async(self.show_window),
                default=True,
            ),
            pystray.MenuItem("Выход", lambda icon, item: self.quit()),
        )
        self.icon = pystray.Icon("z-gui", self._icon_image(), "Z-GUI", menu)
        try:
            self.icon._message_handlers[0x0011] = lambda wparam, lparam: 1
            self.icon._message_handlers[0x0016] = lambda wparam, lparam: self._session_end()
        except Exception:
            pass
        self.icon.run()

    def _session_end(self) -> int:
        self.bridge.stop(3.0)
        return 1

    def shutdown(self) -> None:
        self._stop.set()
        self.bridge.stop()
        if self.server is not None:
            self.server.stop()
            self.server = None
        handle = winapi.find_window("Z-GUI")
        if handle:
            winapi.close_window(handle)
