from __future__ import annotations

from datetime import datetime

from .. import __version__, paths
from ..logs import get_logger
from . import ipset, payload, versions
from . import zapret as zapret_mod
from .locks import FileLock
from .state import StateStore

log = get_logger("z-gui.bootstrap")


def bundle_manifest() -> dict:
    return payload.read_manifest(paths.bundled_payload_dir())


def ensure_ready() -> dict:
    paths.ensure_dirs()
    store = StateStore(paths.state_path())
    source = paths.bundled_payload_dir()
    manifest = payload.read_manifest(paths.payload_dir())
    if source.is_dir():
        manifest = payload.sync_payload(source, paths.payload_dir())
    data = store.read()
    now = datetime.now().replace(microsecond=0).isoformat()
    changes: dict = {"app_version": __version__}
    proxy_version = manifest.get("proxy", {}).get("version")
    if proxy_version and not data.get("proxy_version"):
        changes["proxy_version"] = proxy_version
        changes["proxy_published_at"] = manifest.get("proxy", {}).get("published_at")
    zapret_version = manifest.get("zapret", {}).get("version")
    zapret_date = manifest.get("zapret", {}).get("published_at")
    installed = data.get("zapret_version")
    needs = (
        not zapret_mod.validate_tree(paths.zapret_dir())
        or not installed
        or versions.is_newer(
            zapret_version, zapret_date, installed, data.get("zapret_published_at")
        )
    )
    if zapret_version and needs:
        archive = paths.payload_dir() / "zapret.zip"
        if archive.exists():
            with FileLock(paths.ops_lock_path()):
                current = store.read()
                installed_current = current.get("zapret_version")
                still = (
                    not zapret_mod.validate_tree(paths.zapret_dir())
                    or not installed_current
                    or versions.is_newer(
                        zapret_version,
                        zapret_date,
                        installed_current,
                        current.get("zapret_published_at"),
                    )
                )
                if still:
                    list_path = paths.zapret_dir() / "lists" / "ipset-all.txt"
                    mode = (
                        ipset.mode_of(list_path)
                        if list_path.exists() and installed_current
                        else None
                    )
                    payload.install_zip(archive, paths.zapret_dir(), ipset_mode=mode)
                    changes["zapret_version"] = zapret_version
                    changes["zapret_published_at"] = zapret_date
                    changes["zapret_installed_at"] = now
                    log.info("zapret %s установлен", zapret_version)
    if zapret_mod.validate_tree(paths.zapret_dir()):
        payload.ensure_user_lists(paths.zapret_dir())
    if changes:
        store.update(lambda values: values.update(changes))
    return store.read()
