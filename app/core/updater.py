from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .. import __version__, paths
from ..logs import get_logger
from . import ipset, payload, procs, versions

ZAPRET_REPO = "Flowseal/zapret-discord-youtube"
PROXY_REPO = "Flowseal/tg-ws-proxy"
APP_REPO = "lECL1PS3l/z-gui"
API = "https://api.github.com"

log = get_logger("z-gui.updater")


class UpdateError(RuntimeError):
    pass


def _get_json(url: str) -> dict:
    import httpx

    with httpx.Client(
        timeout=25,
        follow_redirects=True,
        headers={
            "User-Agent": "Z-GUI",
            "Accept": "application/vnd.github+json",
        },
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, dict):
        raise UpdateError("неожиданный ответ GitHub")
    return data


def _release(repo: str) -> dict:
    return _get_json(f"{API}/repos/{repo}/releases/latest")


def latest() -> dict:
    result: dict = {"zapret": None, "proxy": None, "app": None}
    errors: list[str] = []
    try:
        release = _release(ZAPRET_REPO)
        asset = next(
            (
                item
                for item in release.get("assets", [])
                if str(item.get("name", "")).lower().endswith(".zip")
            ),
            None,
        )
        if asset is None:
            raise UpdateError("в релизе Zapret нет zip-архива")
        digest = str(asset.get("digest") or "")
        result["zapret"] = {
            "version": str(release.get("tag_name") or ""),
            "published_at": release.get("published_at"),
            "url": asset.get("browser_download_url"),
            "sha256": digest.split(":", 1)[-1] if digest else "",
            "size": asset.get("size"),
        }
    except Exception as exc:
        errors.append(f"zapret: {exc}")
    try:
        release = _release(PROXY_REPO)
        tag = str(release.get("tag_name") or "")
        result["proxy"] = {
            "version": tag.lstrip("v"),
            "published_at": release.get("published_at"),
            "url": f"{API}/repos/{PROXY_REPO}/zipball/{tag}",
        }
    except Exception as exc:
        errors.append(f"мост: {exc}")
    try:
        release = _release(APP_REPO)
        result["app"] = {
            "version": str(release.get("tag_name") or "").lstrip("v"),
            "published_at": release.get("published_at"),
            "url": release.get("html_url"),
        }
    except Exception as exc:
        errors.append(f"программа: {exc}")
    if not any(result.values()):
        raise UpdateError("; ".join(errors) or "нет данных")
    return result


def build_offer(state: dict, remote: dict) -> dict | None:
    zapret = remote.get("zapret")
    proxy = remote.get("proxy")
    app = remote.get("app")
    zapret_new = bool(
        zapret
        and versions.is_newer(
            zapret.get("version"),
            zapret.get("published_at"),
            state.get("zapret_version"),
            state.get("zapret_published_at"),
        )
    )
    proxy_new = bool(
        proxy
        and versions.is_newer(
            proxy.get("version"),
            proxy.get("published_at"),
            state.get("proxy_version"),
            state.get("proxy_published_at"),
        )
    )
    app_new = bool(
        app
        and versions.is_newer(
            app.get("version"),
            app.get("published_at"),
            __version__,
            None,
        )
    )
    if not (zapret_new or proxy_new or app_new):
        return None
    if app_new:
        label = app["version"]
    elif zapret_new:
        label = zapret["version"]
    else:
        label = proxy["version"]
    return {
        "found_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "label": label,
        "zapret": zapret if zapret_new else None,
        "proxy": proxy if proxy_new else None,
        "app": app if app_new else None,
    }


def check(state: dict) -> dict | None:
    remote = latest()
    return build_offer(state, remote)


def self_command(*args: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, "-m", "app", *args]


def _download(url: str, dest: Path, expected: str = "", progress=None) -> None:
    import httpx

    digest = hashlib.sha256()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream(
        "GET",
        url,
        follow_redirects=True,
        timeout=120,
        headers={"User-Agent": "Z-GUI"},
    ) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length") or 0)
        done = 0
        with open(dest, "wb") as handle:
            for chunk in response.iter_bytes(65536):
                handle.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if total and progress is not None:
                    progress(min(done / total, 1.0))
    if expected and digest.hexdigest() != expected:
        dest.unlink(missing_ok=True)
        raise UpdateError("контрольная сумма не совпала")


def _smoke(directory: Path) -> int:
    env = dict(os.environ)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    try:
        result = subprocess.run(
            self_command("--smoke-proxy", str(directory)),
            timeout=150,
            cwd=str(paths.resource_dir()),
            creationflags=procs.CREATE_NO_WINDOW,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 1
    return int(result.returncode)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _replace_directory(source: Path, target: Path) -> None:
    staging = target.with_name(target.name + ".new")
    old = target.with_name(target.name + ".old")
    shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(old, ignore_errors=True)
    shutil.copytree(source, staging)
    if not (staging / "tg_ws_proxy.py").exists():
        shutil.rmtree(staging, ignore_errors=True)
        raise UpdateError("архив моста повреждён")
    if target.exists():
        target.replace(old)
    try:
        staging.replace(target)
    except OSError:
        if old.exists() and not target.exists():
            old.replace(target)
        raise
    shutil.rmtree(old, ignore_errors=True)


def apply_offer(
    offer: dict,
    zapret,
    store,
    stop_bridge=None,
    start_bridge=None,
    progress=None,
) -> None:
    app = offer.get("app")
    if app and app.get("url"):
        try:
            os.startfile(app["url"])
        except OSError:
            log.warning("не удалось открыть страницу релиза")
    if not offer.get("zapret") and not offer.get("proxy"):
        now = _now()
        store.update(
            lambda values: values.update({"last_check": now, "pending_update": None})
        )
        log.info("обновление программы: %s", offer.get("label"))
        return
    temp = paths.temp_dir() / "update"
    shutil.rmtree(temp, ignore_errors=True)
    temp.mkdir(parents=True, exist_ok=True)
    zapret_zip = None
    zapret_dir = None
    proxy_dir = None
    if offer.get("zapret"):
        zapret_zip = temp / "zapret.zip"
        _download(
            offer["zapret"]["url"],
            zapret_zip,
            offer["zapret"].get("sha256") or "",
            progress,
        )
        zapret_dir = temp / "zapret_tree"
        payload.extract_zip(zapret_zip, zapret_dir)
        if not payload.validate_tree(zapret_dir):
            raise UpdateError("архив Zapret повреждён")
    if offer.get("proxy"):
        proxy_zip = temp / "proxy.zip"
        _download(offer["proxy"]["url"], proxy_zip, "", progress)
        proxy_dir = temp / "proxy_tree"
        payload.extract_zip(proxy_zip, proxy_dir)
        if not (proxy_dir / "proxy" / "tg_ws_proxy.py").exists():
            raise UpdateError("архив моста повреждён")
        if _smoke(proxy_dir) != 0:
            raise UpdateError("мост не прошёл проверку")
    data = store.read()
    was_enabled = bool(data.get("zapret_enabled"))
    strategy = data.get("strategy")
    bridge_was = bool(data.get("bridge_enabled"))
    proxy_source = proxy_dir / "proxy" if proxy_dir is not None else None
    with zapret.lock:
        if proxy_source is not None and stop_bridge is not None:
            try:
                stop_bridge()
            except Exception:
                pass
        if zapret_zip is not None:
            zapret.remove_service()
            list_path = paths.zapret_dir() / "lists" / "ipset-all.txt"
            mode = ipset.mode_of(list_path) if list_path.exists() else None
            payload.install_zip(zapret_zip, paths.zapret_dir(), ipset_mode=mode)
            if mode:
                ipset.set_mode(paths.zapret_dir() / "lists" / "ipset-all.txt", mode)
            try:
                ipset.update_from_remote(paths.zapret_dir() / "lists" / "ipset-all.txt")
            except Exception as exc:
                log.warning("список IPSet не обновлён: %s", exc)
        if proxy_source is not None:
            _replace_directory(proxy_source, paths.payload_dir() / "proxy")
        now = _now()
        manifest = payload.read_manifest(paths.payload_dir())
        updates: dict = {"last_check": now, "pending_update": None}
        if offer.get("zapret"):
            manifest.setdefault("zapret", {}).update(
                {
                    "version": offer["zapret"]["version"],
                    "published_at": offer["zapret"].get("published_at"),
                    "sha256": offer["zapret"].get("sha256"),
                }
            )
            updates["zapret_version"] = offer["zapret"]["version"]
            updates["zapret_published_at"] = offer["zapret"].get("published_at")
            updates["zapret_installed_at"] = now
        if offer.get("proxy"):
            manifest.setdefault("proxy", {}).update(
                {
                    "version": offer["proxy"]["version"],
                    "published_at": offer["proxy"].get("published_at"),
                }
            )
            updates["proxy_version"] = offer["proxy"]["version"]
            updates["proxy_published_at"] = offer["proxy"].get("published_at")
        manifest_path = paths.payload_dir() / "manifest.json"
        manifest_tmp = manifest_path.with_name("manifest.json.tmp")
        manifest_tmp.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(manifest_tmp, manifest_path)
        restored = False
        if was_enabled and zapret_zip is not None:
            try:
                zapret.enable(strategy)
                restored = True
            except Exception as exc:
                log.warning("не удалось вернуть службу: %s", exc)
        store.update(lambda values: values.update(updates))
        if bridge_was and proxy_source is not None and start_bridge is not None:
            try:
                start_bridge()
            except Exception as exc:
                log.warning("не удалось вернуть мост: %s", exc)
        if zapret_zip is not None and was_enabled and not restored:
            raise UpdateError("инструменты установлены, но служба не запустилась")
        log.info("обновление установлено: %s", offer.get("label"))
    shutil.rmtree(temp, ignore_errors=True)
