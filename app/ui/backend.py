from __future__ import annotations

import os
import shutil
import threading
import time
from datetime import datetime, timedelta, timezone

from PySide6.QtCore import Property, QObject, Qt, Signal, Slot

from .. import __version__, command, ipc, paths
from ..core import apply as apply_mod
from ..core import autostart, diagnostics, payload, reconcile, updater, versions
from ..core import strategies as strategies_mod
from ..core.state import StateStore
from ..core.tester import Tester
from ..core.zapret import Zapret, ZapretError
from ..logs import get_logger

log = get_logger("z-gui.backend")
ROWS = 3


class Backend(QObject):
    changed = Signal()
    _relay = Signal(object)

    version = Property(str, lambda self: self._view["version"], notify=changed)
    demo = Property(bool, lambda self: False, constant=True)
    demoTitle = Property(str, lambda self: "", constant=True)
    zapretOn = Property(bool, lambda self: self._view["zapretOn"], notify=changed)
    bridgeOn = Property(bool, lambda self: self._view["bridgeOn"], notify=changed)
    applyLabel = Property(str, lambda self: self._view["applyLabel"], notify=changed)
    gameFilter = Property(bool, lambda self: self._view["gameFilter"], notify=changed)
    autostart = Property(bool, lambda self: self._view["autostart"], notify=changed)
    rows = Property("QVariantList", lambda self: self._view["rows"], notify=changed)
    selected = Property(int, lambda self: self._view["selected"], notify=changed)
    phase = Property(str, lambda self: self._view["phase"], notify=changed)
    testName = Property(str, lambda self: self._view["testName"], notify=changed)
    testCount = Property(str, lambda self: self._view["testCount"], notify=changed)
    testValue = Property(float, lambda self: self._view["testValue"], notify=changed)
    updateVisible = Property(bool, lambda self: self._view["updateVisible"], notify=changed)
    updateLabel = Property(str, lambda self: self._view["updateLabel"], notify=changed)
    updateProgress = Property(float, lambda self: self._view["updateProgress"], notify=changed)
    updateBusy = Property(bool, lambda self: self._view["updateBusy"], notify=changed)
    busy = Property(bool, lambda self: self._view["busy"], notify=changed)
    canTest = Property(bool, lambda self: self._view["canTest"], notify=changed)
    canApply = Property(bool, lambda self: self._view["canApply"], notify=changed)
    canCancel = Property(bool, lambda self: self._view["canCancel"], notify=changed)
    errorTitle = Property(str, lambda self: self._view["errorTitle"], notify=changed)
    errorReason = Property(str, lambda self: self._view["errorReason"], notify=changed)
    errorFix = Property(bool, lambda self: self._view["errorFix"], notify=changed)
    errorRestore = Property(bool, lambda self: self._view["errorRestore"], notify=changed)
    errorClose = Property(bool, lambda self: self._view["errorClose"], notify=changed)

    def __init__(self, store: StateStore) -> None:
        super().__init__()
        self.store = store
        self.zapret = Zapret(store=store)
        self._relay.connect(self._deliver, Qt.QueuedConnection)
        self._view: dict = {}
        self._busy = False
        self._zapret_busy = False
        self._apply_busy = False
        self._phase = "idle"
        self._error: dict | None = None
        self._selected = 0
        self._pending: dict | None = None
        self._update_hidden = False
        self._update_busy = False
        self._update_progress = 0.0
        self._test = {"name": "", "done": 0, "total": 0}
        self._cancel: threading.Event | None = None
        self._bridge = {"running": False, "port": None}
        self._link_opened = False
        self._closed = False
        self._refresh()
        threading.Thread(target=self._poll, name="zgui-poll", daemon=True).start()
        threading.Thread(target=self._boot, name="zgui-boot", daemon=True).start()

    def _post(self, function) -> None:
        self._relay.emit(function)

    def _deliver(self, function) -> None:
        try:
            function()
        except Exception as exc:
            log.warning("ui update: %s", exc)

    def _row(self, item: dict) -> dict:
        total = int(item.get("total") or 0)
        name = strategies_mod.label(str(item.get("name") or ""))
        if total:
            detail = f"{int(item.get('ok') or 0)}/{total}"
            average = item.get("avg_ms")
            if average is not None:
                detail += f" · {average} мс"
        else:
            detail = ""
        return {
            "name": name or "—",
            "detail": detail,
            "id": str(item.get("name") or ""),
        }

    def _bridge_running(self) -> bool:
        return bool((self._bridge or {}).get("running"))

    def _refresh(self) -> None:
        data = self.store.read()
        results = data.get("results") or []
        strategy = str(data.get("strategy") or "general.bat")
        enabled = bool(data.get("zapret_enabled"))
        rows: list[dict] = []
        for index in range(ROWS):
            if index < len(results):
                item = results[index]
                rows.append(self._row(item))
            else:
                detail = "проверка не выполнялась" if index == 0 and not results else ""
                rows.append({"name": "—", "detail": detail, "id": ""})
        if results:
            self._selected = max(0, min(self._selected, len(results) - 1))
        else:
            self._selected = 0
        running = self._bridge_running()
        busy = self._busy or self._zapret_busy or self._apply_busy or self._update_busy
        error = self._error or {}
        action = apply_mod.NOOP
        if results:
            selected = results[min(self._selected, len(results) - 1)]
            action = apply_mod.decision(str(selected.get("name") or ""), strategy, enabled)
        label = "Применить"
        if self._apply_busy:
            label = "Применяем…"
        elif results and action == apply_mod.NOOP:
            label = "Применена"
        elif results and action == apply_mod.ENABLE:
            label = "Включить"
        test_total = int(self._test.get("total") or 0)
        test_done = int(self._test.get("done") or 0)
        self._view = {
            "version": f"Версия {__version__}",
            "zapretOn": enabled,
            "bridgeOn": running,
            "applyLabel": label,
            "gameFilter": bool(data.get("game_filter")),
            "autostart": bool(data.get("autostart")),
            "rows": rows,
            "selected": self._selected,
            "phase": self._phase,
            "testName": str(self._test.get("name") or ""),
            "testCount": f"{test_done} / {test_total}" if test_total else "",
            "testValue": (test_done / test_total) if test_total else 0.0,
            "updateVisible": bool(self._pending) and not self._update_hidden,
            "updateLabel": f"Обновление · {self._pending.get('label', '')}" if self._pending else "",
            "updateProgress": float(self._update_progress),
            "updateBusy": self._update_busy,
            "busy": busy,
            "canTest": not busy and self._phase != "test",
            "canApply": bool(results)
            and not busy
            and self._phase == "idle"
            and action != apply_mod.NOOP,
            "canCancel": self._phase == "test",
            "errorTitle": str(error.get("title") or ""),
            "errorReason": "\n".join(error.get("reason") or []),
            "errorFix": bool(error.get("fix")),
            "errorRestore": bool(error.get("restore")),
            "errorClose": bool(error.get("close")),
        }
        self.changed.emit()

    def _poll(self) -> None:
        while not self._closed:
            response = ipc.call("state", timeout=1.2)
            self._bridge = {
                "running": bool(response and response.get("ok") and response.get("bridge")),
                "port": (response or {}).get("port"),
            }
            self._post(self._refresh)
            time.sleep(3)

    def _boot(self) -> None:
        try:
            reconcile.sync_state(self.store, self.zapret)
        except Exception:
            pass
        data = self.store.read()
        pending = data.get("pending_update")
        if pending:
            self._post(lambda: self._apply_pending(pending))
            return
        last = versions.parse_date(data.get("last_check"))
        now = datetime.now(timezone.utc)
        if last is not None and now - last < timedelta(hours=72):
            return
        try:
            offer = updater.check(data)
        except Exception:
            return
        self.store.set(last_check=now.replace(microsecond=0).isoformat(), pending_update=offer)
        if offer:
            self._post(lambda: self._apply_pending(offer))

    def _apply_pending(self, offer: dict) -> None:
        self._pending = offer
        self._update_hidden = False
        self._refresh()

    def _tools_broken(self) -> bool:
        if not payload.validate_tree(paths.zapret_dir()):
            return True
        return not (paths.payload_dir() / "proxy" / "tg_ws_proxy.py").exists()

    def _clear_error(self) -> None:
        self._error = None
        self._phase = "idle"
        self._refresh()

    def _fail(self, title: str, reason: str = "", retry: str | None = None) -> None:
        findings: list = []
        try:
            findings = diagnostics.collect()
        except Exception:
            findings = []
        lines, fix = diagnostics.brief(findings)
        restore = self._tools_broken() or fix == "restore"
        if fix == "restore":
            fix = None
        text: list[str] = []
        if reason:
            text.append(str(reason))
        for line in lines:
            if len(text) >= 2:
                break
            if line not in text:
                text.append(line)
        if not text:
            text.append("причина не определена")
        text[0] = "Причина: " + text[0]
        self._error = {
            "title": title,
            "reason": text[:2],
            "fix": fix,
            "restore": restore,
            "retry": retry,
            "close": True,
        }
        self._phase = "error"
        self._refresh()

    @Slot()
    def toggleZapret(self) -> None:
        if self._busy or self._zapret_busy or self._phase == "test" or self._update_busy:
            return
        data = self.store.read()
        enabled = bool(data.get("zapret_enabled"))
        strategy = data.get("strategy")
        self._zapret_busy = True
        self._refresh()

        def worker() -> None:
            try:
                if enabled:
                    self.zapret.disable()
                else:
                    self.zapret.enable(strategy)
                self._post(self._clear_error)
            except ZapretError as exc:
                title = "Не удалось выключить Zapret" if enabled else "Не удалось включить Zapret"
                self._post(lambda: self._fail(title, exc.reason, retry=None if enabled else "enable"))
            except Exception as exc:
                self._post(lambda: self._fail("Ошибка Zapret", str(exc)))
            finally:
                self._zapret_busy = False
                self._post(self._refresh)

        threading.Thread(target=worker, name="zgui-zapret", daemon=True).start()

    @Slot()
    def toggleBridge(self) -> None:
        if self._busy or self._zapret_busy or self._phase == "test" or self._update_busy:
            return
        state = ipc.call("state", timeout=2.0) or {}
        running = bool(state.get("bridge"))
        self._zapret_busy = True
        self._refresh()

        def worker() -> None:
            try:
                if running:
                    response = ipc.call("bridge.stop", timeout=8.0)
                    if not response or not response.get("ok"):
                        raise RuntimeError("мост не отвечает")
                    self.store.set(bridge_enabled=False)
                else:
                    if not ipc.ping():
                        command.spawn("--tray")
                        for _ in range(60):
                            if ipc.ping(timeout=0.8):
                                break
                            time.sleep(0.25)
                    response = ipc.call("bridge.start", timeout=45.0)
                    if not response or not response.get("ok"):
                        raise RuntimeError(str((response or {}).get("error") or "мост не запустился"))
                    self.store.set(bridge_enabled=True)
                    link = response.get("link")
                    if link and not self._link_opened:
                        self._link_opened = True
                        try:
                            os.startfile(link)
                        except OSError:
                            pass
                self._post(self._clear_error)
            except Exception as exc:
                title = "Не удалось выключить Telegram" if running else "Не удалось включить Telegram"
                self._post(lambda: self._fail(title, str(exc)))
            finally:
                self._zapret_busy = False
                self._post(self._refresh)

        threading.Thread(target=worker, name="zgui-bridge", daemon=True).start()

    @Slot(bool)
    def setGameFilter(self, enabled: bool) -> None:
        if self._busy or self._zapret_busy or self._phase == "test" or self._update_busy:
            return
        self._zapret_busy = True
        self._refresh()

        def worker() -> None:
            try:
                self.zapret.set_game_filter(bool(enabled))
                self._post(self._clear_error)
            except ZapretError as exc:
                self._post(lambda: self._fail("Не удалось переключить Game Filter", exc.reason, retry="enable"))
            except Exception as exc:
                self._post(lambda: self._fail("Не удалось переключить Game Filter", str(exc)))
            finally:
                self._zapret_busy = False
                self._post(self._refresh)

        threading.Thread(target=worker, name="zgui-filter", daemon=True).start()

    @Slot(bool)
    def setAutostart(self, enabled: bool) -> None:
        if self._update_busy:
            return
        self.store.set(autostart=bool(enabled))

        def worker() -> None:
            try:
                ok = autostart.sync(bool(enabled))
                if not ok and enabled:
                    self._post(lambda: self._fail("Не удалось добавить автозапуск", "задача планировщика не создана"))
            finally:
                self._post(self._refresh)

        threading.Thread(target=worker, name="zgui-autostart", daemon=True).start()

    @Slot()
    def startTest(self) -> None:
        if self._busy or self._phase == "test" or self._update_busy:
            return
        if not payload.validate_tree(paths.zapret_dir()):
            self._fail("Не удалось запустить Zapret", "файлы Zapret не найдены")
            return
        cancel = threading.Event()
        self._cancel = cancel
        self._phase = "test"
        self._test = {"name": "", "done": 0, "total": 0}
        self._busy = True
        self._error = None
        self._refresh()

        def progress(done: int, total: int, name: str) -> None:
            self._post(lambda: self._test_progress(done, total, name))

        def worker() -> None:
            tester = Tester(self.zapret, self.store, cancel)
            try:
                result = tester.run(progress)
                self._post(lambda: self._test_finished(result))
            except Exception as exc:
                self._post(lambda: self._test_failed(str(exc)))
            finally:
                self._post(self._test_cleanup)

        threading.Thread(target=worker, name="zgui-test", daemon=True).start()

    def _test_progress(self, done: int, total: int, name: str) -> None:
        self._test = {
            "name": strategies_mod.label(name),
            "done": int(done),
            "total": int(total),
        }
        self._refresh()

    def _test_cleanup(self) -> None:
        self._busy = False
        self._cancel = None
        self._refresh()

    def _test_finished(self, result: dict) -> None:
        self._phase = "idle"
        if result.get("cancelled"):
            self._selected = 0
            self._error = None
            self._refresh()
            return
        self._selected = 0
        results = result.get("results") or []
        best = results[0] if results else None
        if not best or int(best.get("ok") or 0) == 0:
            restore = self._tools_broken()
            self._error = {
                "title": "Не удалось подобрать стратегию",
                "reason": [
                    "Причина: ни одна стратегия не прошла проверку",
                    "проверьте конфликтующие программы",
                ],
                "fix": None,
                "restore": restore,
                "retry": None,
                "close": not restore,
            }
            self._phase = "error"
        self._refresh()

    def _test_failed(self, reason: str) -> None:
        self._phase = "idle"
        self._fail("Тест прерван", reason)

    @Slot(int)
    def selectRow(self, index: int) -> None:
        data = self.store.read()
        results = data.get("results") or []
        if not results:
            return
        if 0 <= int(index) < min(ROWS, len(results)):
            self._selected = int(index)
            self._refresh()

    @Slot()
    def applyStrategy(self) -> None:
        if self._busy or self._update_busy or self._apply_busy or self._phase != "idle":
            return
        data = self.store.read()
        results = data.get("results") or []
        if not results:
            return
        index = max(0, min(self._selected, len(results) - 1))
        name = str(results[index].get("name") or "")
        if not name:
            return
        enabled = bool(data.get("zapret_enabled"))
        action = apply_mod.decision(
            strategies_mod.pick(paths.zapret_dir(), name),
            strategies_mod.pick(paths.zapret_dir(), data.get("strategy")),
            enabled,
        )
        if action == apply_mod.NOOP:
            self._refresh()
            return
        self._apply_busy = True
        self._refresh()

        def worker() -> None:
            try:
                chosen = self.zapret.apply_strategy(name)
                if not enabled:
                    self.zapret.enable(chosen)
                self._post(self._applied)
            except ZapretError as exc:
                self._post(lambda: self._fail("Не удалось применить стратегию", exc.reason, retry="enable"))
            except Exception as exc:
                self._post(lambda: self._fail("Не удалось применить стратегию", str(exc)))
            finally:
                self._apply_busy = False
                self._post(self._refresh)

        threading.Thread(target=worker, name="zgui-apply", daemon=True).start()

    def _applied(self) -> None:
        self._phase = "idle"
        self._error = None
        self._refresh()

    @Slot()
    def cancelTest(self) -> None:
        cancel = self._cancel
        if cancel is not None:
            cancel.set()
        self._refresh()

    @Slot()
    def fixError(self) -> None:
        if not self._error or self._zapret_busy:
            return
        code = self._error.get("fix")
        retry = self._error.get("retry")
        self._zapret_busy = True
        self._refresh()

        def worker() -> None:
            try:
                fixed = diagnostics.apply_fix(str(code)) if code else False
                if not fixed:
                    self._post(lambda: self._fail("Исправление не помогло", "", retry=retry))
                elif retry == "enable":
                    self.zapret.enable(self.store.read().get("strategy"))
                    self._post(self._clear_error)
                else:
                    self._post(self._clear_error)
            except ZapretError as exc:
                self._post(lambda: self._fail("Не удалось включить Zapret", exc.reason, retry="enable"))
            except Exception as exc:
                self._post(lambda: self._fail("Не удалось выполнить исправление", str(exc)))
            finally:
                self._zapret_busy = False
                self._post(self._refresh)

        threading.Thread(target=worker, name="zgui-fix", daemon=True).start()

    @Slot()
    def restoreTools(self) -> None:
        if self._zapret_busy or self._update_busy:
            return
        self._zapret_busy = True
        self._refresh()

        def worker() -> None:
            try:
                source = paths.bundled_payload_dir()
                archive = paths.payload_dir() / "zapret.zip"
                if not archive.exists():
                    origin = source / "zapret.zip"
                    if not origin.exists():
                        raise ZapretError("Архив восстановления не найден")
                    shutil.copy2(origin, archive)
                with self.zapret.lock:
                    payload.install_zip(archive, paths.zapret_dir())
                    proxy_source = source / "proxy"
                    if proxy_source.is_dir():
                        target = paths.payload_dir() / "proxy"
                        shutil.rmtree(target, ignore_errors=True)
                        shutil.copytree(proxy_source, target)
                    manifest = payload.read_manifest(source) or payload.read_manifest(paths.payload_dir())
                    data = self.store.read()
                    updates: dict = {}
                    if manifest.get("zapret", {}).get("version"):
                        updates["zapret_version"] = manifest["zapret"]["version"]
                        updates["zapret_published_at"] = manifest["zapret"].get("published_at")
                    if manifest.get("proxy", {}).get("version"):
                        updates["proxy_version"] = manifest["proxy"]["version"]
                        updates["proxy_published_at"] = manifest["proxy"].get("published_at")
                    if updates:
                        self.store.update(lambda values: values.update(updates))
                    if data.get("zapret_enabled"):
                        self.zapret.enable(data.get("strategy"))
                self._post(self._clear_error)
            except ZapretError as exc:
                self._post(lambda: self._fail("Не удалось восстановить", exc.reason))
            except Exception as exc:
                self._post(lambda: self._fail("Не удалось восстановить", str(exc)))
            finally:
                self._zapret_busy = False
                self._post(self._refresh)

        threading.Thread(target=worker, name="zgui-restore", daemon=True).start()

    @Slot()
    def demoNext(self) -> None:
        pass

    @Slot()
    def demoPrev(self) -> None:
        pass

    @Slot()
    def dismissError(self) -> None:
        self._error = None
        self._phase = "idle"
        self._refresh()

    @Slot()
    def updateNow(self) -> None:
        if not self._pending or self._update_busy:
            return
        offer = self._pending
        self._update_busy = True
        self._update_progress = 0.0
        self._refresh()

        def progress(value: float) -> None:
            self._post(lambda: self._set_progress(value))

        def stop_bridge() -> None:
            response = ipc.call("bridge.stop", timeout=8.0)
            if response and response.get("ok"):
                self.store.set(bridge_enabled=False)

        def start_bridge() -> None:
            response = ipc.call("bridge.start", timeout=45.0)
            if response and response.get("ok"):
                self.store.set(bridge_enabled=True)

        def worker() -> None:
            try:
                updater.apply_offer(
                    offer,
                    self.zapret,
                    self.store,
                    stop_bridge=stop_bridge,
                    start_bridge=start_bridge,
                    progress=progress,
                )
                self._post(self._update_done)
            except Exception as exc:
                self._post(lambda: self._update_failed(str(exc)))
            finally:
                self._update_busy = False
                self._post(self._refresh)

        threading.Thread(target=worker, name="zgui-update", daemon=True).start()

    def _set_progress(self, value: float) -> None:
        self._update_progress = max(0.0, min(float(value), 1.0))
        self._refresh()

    def _update_done(self) -> None:
        self._pending = None
        self._update_hidden = True
        self._update_progress = 1.0
        self._phase = "idle"
        self._error = None
        self._refresh()

    def _update_failed(self, reason: str) -> None:
        self._update_busy = False
        self._fail("Не удалось обновить", reason)

    @Slot()
    def updateLater(self) -> None:
        self._update_hidden = True
        self._refresh()

    @Slot(int, int)
    def saveWindowPos(self, x: int, y: int) -> None:
        self.store.set(window=[int(x), int(y)])

    def shutdown(self) -> None:
        self._closed = True
        cancel = self._cancel
        if cancel is not None:
            cancel.set()
            deadline = time.monotonic() + 20
            while self._busy and time.monotonic() < deadline:
                time.sleep(0.1)
