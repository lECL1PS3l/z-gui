from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

from .. import paths
from ..logs import get_logger
from . import batparse, gamefilter, payload, procs, strategies
from .locks import FileLock
from .state import StateStore

SRVC = "zapret"
DESCRIPTION = "Zapret DPI bypass software"
VALUE_NAME = "zapret-discord-youtube"
STATE_RE = re.compile(
    r"\b(RUNNING|STOPPED|START_PENDING|STOP_PENDING|PAUSED|PAUSED_PENDING|CONTINUE_PENDING)\b"
)

log = get_logger("z-gui.zapret")


class ZapretError(RuntimeError):
    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.reason = (reason or message).strip()


def service_status(text: str, code: int) -> str:
    if code != 0 and "1060" in text:
        return "missing"
    match = STATE_RE.search(text or "")
    if not match:
        return "missing"
    token = match.group(1)
    if token in ("RUNNING", "START_PENDING", "CONTINUE_PENDING"):
        return "running"
    return "stopped"


def validate_tree(root: Path) -> bool:
    root = Path(root)
    return (
        (root / "bin" / "winws.exe").exists()
        and (root / "service.bat").exists()
        and any(root.glob("general*.bat"))
        and (root / "bin" / "WinDivert64.sys").exists()
    )


def tcp_timestamps_enabled() -> bool | None:
    result = procs.run(["netsh.exe", "interface", "tcp", "show", "global"], timeout=15)
    for line in result.text.splitlines():
        if "1323" in line or "timestamps" in line.lower():
            lowered = line.lower()
            if "enabled" in lowered or "включ" in lowered:
                return True
            if "disabled" in lowered or "отключ" in lowered:
                return False
    return None


def enable_tcp_timestamps() -> bool:
    result = procs.run(
        ["netsh.exe", "interface", "tcp", "set", "global", "timestamps=enabled"],
        timeout=15,
    )
    return result.code == 0


def _first_line(text: str) -> str:
    for line in (text or "").splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned[:120]
    return ""


class Zapret:
    def __init__(
        self,
        root: Path | None = None,
        store: StateStore | None = None,
        lock_path: Path | None = None,
    ) -> None:
        self.root = Path(root) if root else paths.zapret_dir()
        self.store = store or StateStore(paths.state_path())
        self._lock = FileLock(lock_path or paths.ops_lock_path())

    @property
    def winws(self) -> Path:
        return self.root / "bin" / "winws.exe"

    @property
    def lock(self) -> FileLock:
        return self._lock

    @property
    def lists(self) -> Path:
        return self.root / "lists"

    @property
    def game_path(self) -> Path:
        return self.root / "utils" / "game_filter.enabled"

    def _sc(self, *args: str, timeout: float = 30.0) -> procs.Result:
        return procs.run(["sc.exe", *args], timeout=timeout)

    def status(self) -> str:
        result = self._sc("query", SRVC, timeout=15)
        return service_status(result.text, result.code)

    def is_running(self) -> bool:
        return self.status() == "running" or procs.winws_running()

    def strategies(self) -> list[Path]:
        return strategies.list_files(self.root)

    def game_filter(self) -> gamefilter.GameFilter:
        return gamefilter.parse_file(self.game_path)

    def argv_for(self, name: str) -> list[str]:
        game = self.game_filter()
        return batparse.parse_file(
            self.root / name,
            game.tcp_value,
            game.udp_value,
        )

    def _clean_windivert(self) -> None:
        if procs.winws_running():
            return
        marker = str(self.root).replace("/", "\\").lower()
        for name in ("WinDivert", "WinDivert14"):
            query = self._sc("qc", name, timeout=10)
            text = query.text.replace("/", "\\").lower()
            if query.code != 0 or marker not in text:
                continue
            self._sc("stop", name, timeout=10)
            self._sc("delete", name, timeout=10)

    def remove_service(self) -> None:
        self._sc("stop", SRVC, timeout=25)
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if self.status() in ("missing", "stopped"):
                break
            time.sleep(0.3)
        self._sc("delete", SRVC, timeout=25)
        procs.kill_winws()
        self._clean_windivert()

    def _write_registry(self, strategy_stem: str) -> None:
        try:
            import winreg

            key = winreg.CreateKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"System\CurrentControlSet\Services\zapret",
            )
            with key:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, strategy_stem)
        except OSError:
            log.warning("не удалось записать имя стратегии в реестр")

    def _create_service(self, strategy: str) -> None:
        argv = self.argv_for(strategy)
        binpath = subprocess.list2cmdline([str(self.winws), *argv])
        result = self._sc(
            "create",
            SRVC,
            "binPath=",
            binpath,
            "DisplayName=",
            "zapret",
            "start=",
            "auto",
        )
        if result.code != 0:
            raise ZapretError(
                "Не удалось создать службу Zapret",
                _first_line(result.text) or "sc.exe create завершился с ошибкой",
            )
        self._sc("description", SRVC, DESCRIPTION)
        self._sc("start", SRVC, timeout=25)

    def _wait_running(self, timeout: float = 15.0) -> bool:
        deadline = time.monotonic() + timeout
        seen = False
        while time.monotonic() < deadline:
            if procs.winws_running():
                seen = True
                time.sleep(0.8)
                if procs.winws_running():
                    return True
            if self.status() == "running" and not seen:
                time.sleep(0.5)
                if procs.winws_running() or self.status() == "running":
                    return True
            time.sleep(0.4)
        return False

    def _enable_locked(self, strategy: str | None) -> str:
        if not validate_tree(self.root):
            raise ZapretError("Файлы Zapret не найдены", "требуется восстановление")
        payload.ensure_user_lists(self.root)
        chosen = strategies.pick(self.root, strategy)
        if not (self.root / chosen).exists():
            raise ZapretError("Стратегия не найдена", chosen)
        self.remove_service()
        enable_tcp_timestamps()
        self._create_service(chosen)
        if not self._wait_running():
            self.remove_service()
            raise ZapretError(
                "Служба Zapret не запустилась",
                "проверьте конфликтующие программы и драйвер",
            )
        self._write_registry(Path(chosen).stem)
        log.info("служба zapret запущена: %s", chosen)
        return chosen

    def enable(self, strategy: str | None = None) -> str:
        with self._lock:
            chosen = self._enable_locked(strategy)
            self.store.set(zapret_enabled=True, strategy=chosen)
            return chosen

    def disable(self) -> None:
        with self._lock:
            self.remove_service()
            self.store.set(zapret_enabled=False)
            log.info("служба zapret остановлена")

    def restart(self) -> str:
        with self._lock:
            data = self.store.read()
            chosen = self._enable_locked(data.get("strategy"))
            self.store.set(zapret_enabled=True, strategy=chosen)
            return chosen

    def stop_tools(self) -> None:
        with self._lock:
            self.remove_service()

    def set_game_filter(self, enabled: bool) -> None:
        with self._lock:
            game = gamefilter.parse_file(self.game_path)
            gamefilter.write_mode(self.game_path, game, enabled)
            self.store.set(game_filter=bool(enabled))
            data = self.store.read()
            if data.get("zapret_enabled") or self.status() == "running":
                chosen = self._enable_locked(data.get("strategy"))
                self.store.set(zapret_enabled=True, strategy=chosen)

    def apply_strategy(self, name: str) -> str:
        with self._lock:
            data = self.store.read()
            chosen = strategies.pick(self.root, name)
            self.store.set(strategy=chosen)
            if data.get("zapret_enabled") or self.status() == "running":
                chosen = self._enable_locked(chosen)
                self.store.set(zapret_enabled=True, strategy=chosen)
            return chosen
