from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .. import paths
from . import procs
from .zapret import enable_tcp_timestamps, tcp_timestamps_enabled


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    text: str
    fix: str | None = None


def _service_names() -> list[str]:
    try:
        import psutil

        return [service.name().lower() for service in psutil.win_service_iter()]
    except Exception:
        return []


def _process_names() -> list[str]:
    try:
        import psutil

        names: list[str] = []
        for proc in psutil.process_iter(["name"]):
            try:
                names.append(str(proc.info.get("name") or "").lower())
            except psutil.Error:
                continue
        return names
    except Exception:
        return []


def _system_gateway_enabled() -> bool:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "ProxyEnable")
            return int(value) == 1
    except OSError:
        return False


def _doh_configured() -> bool:
    try:
        import winreg

        base = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Services\Dnscache\InterfaceSpecificParameters",
        )
    except OSError:
        return True
    try:
        with base:
            index = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(base, index)
                except OSError:
                    break
                index += 1
                try:
                    with winreg.OpenKey(base, subkey_name) as subkey:
                        try:
                            value, _ = winreg.QueryValueEx(subkey, "DohFlags")
                        except OSError:
                            continue
                        if int(value) > 0:
                            return True
                except OSError:
                    continue
    except OSError:
        return True
    return False


def collect(root: Path | None = None) -> list[Finding]:
    target = Path(root) if root else paths.zapret_dir()
    findings: list[Finding] = []
    bfe = procs.run(["sc.exe", "query", "BFE"], timeout=10)
    if "RUNNING" not in bfe.text:
        findings.append(
            Finding("bfe", "error", "Не запущена служба Base Filtering Engine", "start_bfe")
        )
    if tcp_timestamps_enabled() is False:
        findings.append(
            Finding("tcp_timestamps", "warning", "Отключены метки времени TCP", "tcp_timestamps")
        )
    services = _service_names()
    processes = _process_names()
    if any("adguard" in name for name in processes):
        findings.append(Finding("adguard", "warning", "Adguard может мешать подключению"))
    if any("killer" in name for name in services):
        findings.append(Finding("killer", "warning", "Службы Killer мешают подключению"))
    if any("intel" in name and "connectivity" in name for name in services):
        findings.append(
            Finding("intel", "warning", "Служба Intel Connectivity мешает подключению")
        )
    if any(name in ("tracsrvwrapper", "epwd") for name in services):
        findings.append(Finding("checkpoint", "warning", "Службы Check Point мешают подключению"))
    if any("smartbyte" in name for name in services):
        findings.append(Finding("smartbyte", "warning", "SmartByte мешает подключению"))
    if any("vpn" in name or name == "happservice" for name in services):
        findings.append(
            Finding("tunnel", "warning", "Найдено сетевое ПО, которое может мешать подключению")
        )
    if not (target / "bin" / "WinDivert64.sys").exists():
        findings.append(
            Finding("windivert_file", "error", "Не найден драйвер WinDivert64.sys", "restore")
        )
    if not procs.winws_running():
        windivert = procs.run(["sc.exe", "query", "WinDivert"], timeout=10)
        if "RUNNING" in windivert.text:
            findings.append(
                Finding(
                    "windivert_orphan",
                    "error",
                    "Драйвер занят другим процессом",
                    "clean_windivert",
                )
            )
    conflicts = [
        name
        for name in ("goodbyedpi", "discordfix_zapret", "winws1", "winws2")
        if name in services
    ]
    if conflicts:
        findings.append(
            Finding("conflicts", "error", "Мешают службы: " + ", ".join(conflicts))
        )
    if _system_gateway_enabled():
        findings.append(
            Finding("system_gateway", "warning", "В системе включён промежуточный сервер")
        )
    if not _doh_configured():
        findings.append(Finding("dns", "warning", "Проверьте настройки защищённого DNS"))
    return findings


def brief(findings: list[Finding]) -> tuple[list[str], str | None]:
    errors = [item for item in findings if item.severity == "error"]
    warnings = [
        item for item in findings if item.severity == "warning" and item.code != "dns"
    ]
    others = [item for item in findings if item.severity == "warning" and item.code == "dns"]
    ordered = errors + warnings + others
    lines = [item.text for item in ordered[:2]]
    fix = next((item.fix for item in ordered if item.fix), None)
    return lines, fix


def apply_fix(code: str) -> bool:
    if code == "start_bfe":
        return procs.run(["sc.exe", "start", "BFE"], timeout=25).code == 0
    if code == "tcp_timestamps":
        return enable_tcp_timestamps()
    if code == "clean_windivert":
        if procs.winws_running():
            return False
        ok = True
        for name in ("WinDivert", "WinDivert14"):
            procs.run(["sc.exe", "stop", name], timeout=15)
            result = procs.run(["sc.exe", "delete", name], timeout=15)
            ok = ok and (result.code == 0 or "1060" in result.text)
        return ok
    return False
