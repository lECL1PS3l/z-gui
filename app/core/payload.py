from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from . import ipset, versions

PRESERVED = (
    "lists/list-general-user.txt",
    "lists/list-exclude-user.txt",
    "lists/ipset-exclude-user.txt",
    "utils/game_filter.enabled",
)

USER_LISTS = {
    "lists/ipset-exclude-user.txt": "203.0.113.113/32\n",
    "lists/list-general-user.txt": "# Never leave this file empty\ndomain.example.abc\n",
    "lists/list-exclude-user.txt": "domain.example.abc\n",
}


class PayloadError(RuntimeError):
    pass


def read_manifest(root: Path) -> dict:
    try:
        data = json.loads((Path(root) / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = []
    for info in archive.infolist():
        name = info.filename.replace("\\", "/")
        parts = [part for part in name.split("/") if part]
        if name.startswith("/") or ".." in parts:
            raise PayloadError("небезопасный путь в архиве")
        members.append(info)
    return members


def extract_zip(zip_path: Path, dest: Path) -> None:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        members = _safe_members(archive)
        names = [info.filename.replace("\\", "/") for info in members]
        files = [name for name in names if not name.endswith("/")]
        tops = {name.split("/")[0] for name in files}
        strip = len(tops) == 1 and all("/" in name for name in files)
        prefix = next(iter(tops)) + "/" if strip else ""
        for info in members:
            name = info.filename.replace("\\", "/")
            if prefix:
                if not name.startswith(prefix):
                    continue
                name = name[len(prefix):]
            if not name or name.endswith("/"):
                continue
            target = dest / Path(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, open(target, "wb") as sink:
                shutil.copyfileobj(source, sink)


def validate_tree(root: Path) -> bool:
    root = Path(root)
    return (
        (root / "bin" / "winws.exe").exists()
        and (root / "service.bat").exists()
        and any(root.glob("general*.bat"))
        and (root / "bin" / "WinDivert64.sys").exists()
    )


def _preserve(dest: Path) -> dict[str, bytes]:
    saved: dict[str, bytes] = {}
    for relative in PRESERVED:
        path = dest / Path(relative)
        try:
            saved[relative] = path.read_bytes()
        except OSError:
            continue
    return saved


def _restore(dest: Path, saved: dict[str, bytes]) -> None:
    for relative, data in saved.items():
        path = dest / Path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def ensure_user_lists(dest: Path) -> None:
    dest = Path(dest)
    for relative, content in USER_LISTS.items():
        path = dest / Path(relative)
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\r\n") as handle:
            handle.write(content)


def install_zip(zip_path: Path, dest: Path, ipset_mode: str | None = None) -> None:
    zip_path = Path(zip_path)
    dest = Path(dest)
    if not zip_path.exists():
        raise PayloadError("архив Zapret не найден")
    staging = dest.parent / (dest.name + ".staging")
    backup = dest.parent / (dest.name + ".backup")
    shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(backup, ignore_errors=True)
    try:
        extract_zip(zip_path, staging)
        if not validate_tree(staging):
            raise PayloadError("в архиве нет нужных файлов")
        saved = _preserve(dest) if dest.exists() else {}
        if dest.exists():
            dest.replace(backup)
        try:
            staging.replace(dest)
        except OSError:
            if backup.exists() and not dest.exists():
                backup.replace(dest)
            raise
        _restore(dest, saved)
        ensure_user_lists(dest)
        if ipset_mode:
            ipset.set_mode(dest / "lists" / "ipset-all.txt", ipset_mode)
        shutil.rmtree(backup, ignore_errors=True)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        if not dest.exists() and backup.exists():
            backup.replace(dest)
        raise


def sync_payload(src: Path, dst: Path) -> dict:
    src = Path(src)
    dst = Path(dst)
    dst.mkdir(parents=True, exist_ok=True)
    src_manifest = read_manifest(src)
    dst_manifest = read_manifest(dst)
    changed = False
    archive = src / "zapret.zip"
    if archive.exists():
        src_version = src_manifest.get("zapret", {}).get("version")
        dst_version = dst_manifest.get("zapret", {}).get("version")
        want = not (dst / "zapret.zip").exists() or (
            versions.parse_version(src_version) > versions.parse_version(dst_version)
        )
        if want:
            shutil.copy2(archive, dst / "zapret.zip")
            dst_manifest.setdefault("zapret", {}).update(src_manifest.get("zapret", {}))
            changed = True
    proxy_src = src / "proxy"
    if proxy_src.is_dir():
        src_version = src_manifest.get("proxy", {}).get("version")
        dst_version = dst_manifest.get("proxy", {}).get("version")
        want = not (dst / "proxy" / "tg_ws_proxy.py").exists() or (
            versions.parse_version(src_version) > versions.parse_version(dst_version)
        )
        if want:
            target = dst / "proxy"
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(proxy_src, target)
            dst_manifest.setdefault("proxy", {}).update(src_manifest.get("proxy", {}))
            changed = True
    if changed or not (dst / "manifest.json").exists():
        (dst / "manifest.json").write_text(
            json.dumps(dst_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return dst_manifest
