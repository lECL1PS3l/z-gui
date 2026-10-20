from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from ..logs import get_logger
from . import payload
from . import procs
from . import targets as targets_mod

log = get_logger("z-gui.tester")

CURL = shutil.which("curl.exe") or r"C:\Windows\System32\curl.exe"
PING = shutil.which("ping.exe") or r"C:\Windows\System32\PING.EXE"

VARIANTS = (
    ("http11", ("--http1.1",)),
    ("tls12", ("--tlsv1.2", "--tls-max", "1.2")),
    ("tls13", ("--tlsv1.3", "--tls-max", "1.3")),
)
UNSUP_MARKERS = (
    "not supported",
    "unsupported",
    "schannel",
    "unknown option",
    "unrecognized option",
    "unsupported option",
    "unsupported feature",
)
SSL_CODES = (6, 51, 58, 59, 60, 77, 83, 90, 91)
OUTPUT_RE = re.compile(r"^(\d{3})\s+([0-9]+(?:[.,][0-9]+)?)\s*$")
PING_RE = re.compile(r"[=<]\s*(\d+(?:[.,]\d+)?)\s*(?:ms|мс)", re.IGNORECASE)


@dataclass(frozen=True)
class Check:
    target: str
    kind: str
    status: str
    ms: float | None = None


def kinds_for(target: targets_mod.Target) -> list[str]:
    if target.ping:
        return ["ping"]
    return [kind for kind, _ in VARIANTS]


def classify(code: int, text: str) -> str:
    lowered = (text or "").lower()
    if code == 0:
        return "OK"
    if code == 35:
        return "UNSUP"
    if any(marker in lowered for marker in UNSUP_MARKERS):
        return "UNSUP"
    if code in SSL_CODES:
        return "SSL"
    if "certificate" in lowered or "could not resolve" in lowered or "resolve host" in lowered:
        return "SSL"
    return "ERROR"


def parse_curl_output(text: str) -> tuple[int | None, float | None]:
    for line in reversed((text or "").splitlines()):
        match = OUTPUT_RE.match(line.strip())
        if match:
            return int(match.group(1)), float(match.group(2).replace(",", "."))
    return None, None


def parse_ping_output(text: str) -> float | None:
    match = PING_RE.search(text or "")
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def build_result(name: str, checks: list[Check]) -> dict:
    ok = sum(1 for check in checks if check.status == "OK")
    errors = sum(1 for check in checks if check.status in ("SSL", "ERROR"))
    times = [check.ms for check in checks if check.status == "OK" and check.ms is not None]
    average = int(round(sum(times) / len(times))) if times else None
    return {
        "name": name,
        "ok": ok,
        "errors": errors,
        "total": len(checks),
        "avg_ms": average,
    }


def sort_results(results: list[dict]) -> list[dict]:
    return sorted(
        results,
        key=lambda row: (
            -int(row.get("ok") or 0),
            int(row.get("errors") or 0),
            row.get("avg_ms") if row.get("avg_ms") is not None else 10**9,
            str(row.get("name") or "").lower(),
        ),
    )


def run_matrix(
    names: list[str],
    endpoints: list,
    start,
    stop,
    check_target,
    progress=None,
    cancel: threading.Event | None = None,
    workers: int = 8,
) -> list[dict]:
    results: list[dict] = []
    for index, name in enumerate(names):
        if cancel is not None and cancel.is_set():
            break
        try:
            started = bool(start(name))
        except Exception:
            started = False
        checks: list[Check] = []
        try:
            if started:
                with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
                    futures = {pool.submit(check_target, target): target for target in endpoints}
                    for future in as_completed(futures):
                        target = futures[future]
                        try:
                            checks.extend(future.result())
                        except Exception:
                            checks.extend(
                                Check(target.name, kind, "ERROR") for kind in kinds_for(target)
                            )
            else:
                for target in endpoints:
                    checks.extend(
                        Check(target.name, kind, "ERROR", None) for kind in kinds_for(target)
                    )
        finally:
            stop()
        results.append(build_result(name, checks))
        if progress is not None:
            progress(index + 1, len(names), name)
    return results


class Tester:
    def __init__(self, zapret, store, cancel: threading.Event | None = None) -> None:
        self.zapret = zapret
        self.store = store
        self.cancel = cancel or threading.Event()
        self._proc = None

    def _start(self, name: str) -> bool:
        argv = self.zapret.argv_for(name)
        for arg in argv:
            for prefix in ("--hostlist=", "--hostlist-exclude=", "--ipset=", "--ipset-exclude="):
                if arg.startswith(prefix):
                    path = Path(arg.split("=", 1)[1])
                    if not path.exists():
                        log.warning("стратегия %s: нет файла списка %s", name, path)
        error_path = self.zapret.root.parent / "temp" / "winws-stderr.txt"
        error_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(error_path, "wb")
        try:
            self._proc = subprocess.Popen(
                [str(self.zapret.winws), *argv],
                cwd=str(self.zapret.root / "bin"),
                creationflags=procs.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=handle,
            )
        finally:
            handle.close()
        time.sleep(0.45)
        code = self._proc.poll()
        if code is not None:
            detail = ""
            try:
                detail = error_path.read_text(encoding="utf-8", errors="replace").strip()[-400:]
            except OSError:
                pass
            log.warning("стратегия %s: winws завершился (код %s) %s", name, code, detail)
            return False
        return True

    def _stop(self) -> None:
        procs.kill_winws()
        time.sleep(0.6)

    def _curl(self, target, kind: str, flags: tuple[str, ...]) -> Check:
        result = procs.run(
            [
                CURL,
                "-I",
                "-s",
                "-m",
                "4",
                "--connect-timeout",
                "2",
                "-o",
                "NUL",
                "--show-error",
                "-w",
                "%{http_code} %{time_total}",
                *flags,
                target.url,
            ],
            timeout=8,
        )
        http_code, seconds = parse_curl_output(result.out)
        if result.code == 0 and http_code is not None and http_code >= 100:
            status = "OK"
        else:
            status = classify(result.code, result.text)
        milliseconds = seconds * 1000 if seconds is not None else None
        return Check(target.name, kind, status, milliseconds)

    def _ping(self, target) -> Check:
        result = procs.run([PING, "-n", "1", "-w", "1000", target.ping], timeout=6)
        ok = result.code == 0 and "ttl" in result.text.lower()
        return Check(target.name, "ping", "OK" if ok else "ERROR", parse_ping_output(result.text) if ok else None)

    def _check_target(self, target) -> list[Check]:
        if target.ping:
            return [self._ping(target)]
        if self.cancel.is_set():
            return []
        return [self._curl(target, kind, flags) for kind, flags in VARIANTS]

    def baseline(self, endpoints: list) -> dict:
        urls = [target for target in endpoints if target.url]
        good = 0
        for target in urls:
            if self.cancel.is_set():
                break
            result = procs.run(
                [
                    CURL,
                    "-I",
                    "-s",
                    "-m",
                    "2",
                    "--connect-timeout",
                    "2",
                    "-o",
                    "NUL",
                    "-w",
                    "%{http_code}",
                    "--tlsv1.2",
                    "--tls-max",
                    "1.2",
                    target.url,
                ],
                timeout=5,
            )
            if result.code == 0 and re.match(r"^\d{3}$", result.out.strip()):
                good += 1
        return {"ok": good, "total": len(urls)}

    def run(self, progress=None) -> dict:
        target_path = self.zapret.root / "utils" / "targets.txt"
        endpoints = targets_mod.parse_file(target_path)
        names = [path.name for path in self.zapret.strategies()]
        data = self.store.read()
        was_enabled = bool(data.get("zapret_enabled"))
        previous = data.get("strategy")
        previous_results = data.get("results") or []
        previous_baseline = data.get("baseline")
        baseline: dict = {}
        results: list[dict] = previous_results
        cancelled = False
        restored = False
        log.info("тест: %s стратегий, %s целей", len(names), len(endpoints))
        with self.zapret.lock:
            payload.ensure_user_lists(self.zapret.root)
            self.zapret.remove_service()
            try:
                baseline = self.baseline(endpoints)
                results = run_matrix(
                    names,
                    endpoints,
                    self._start,
                    self._stop,
                    self._check_target,
                    progress=progress,
                    cancel=self.cancel,
                )
                cancelled = self.cancel.is_set()
                if cancelled:
                    results = previous_results
                else:
                    results = sort_results(results)
            finally:
                self.zapret.remove_service()
                if was_enabled:
                    try:
                        self.zapret.enable(previous)
                        restored = True
                    except Exception as exc:
                        log.warning("не удалось вернуть службу: %s", exc)
                self.store.set(
                    results=results,
                    baseline=previous_baseline if cancelled else baseline,
                    zapret_enabled=restored,
                )
        best = results[0]["name"] if results else "—"
        log.info("тест завершён: %s, лучшая %s", "отменён" if cancelled else "готов", best)
        return {
            "results": results,
            "baseline": baseline,
            "cancelled": cancelled,
            "restored": restored,
        }
