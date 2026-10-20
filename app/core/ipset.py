from __future__ import annotations

from pathlib import Path

MARKER = "203.0.113.113/32"
REMOTE_URL = (
    "https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube"
    "/refs/heads/main/.service/ipset-service.txt"
)


class IpsetError(RuntimeError):
    pass


def detect(text: str) -> str:
    if not text.strip():
        return "any"
    if MARKER in text:
        return "none"
    return "loaded"


def mode_of(path: Path) -> str:
    try:
        return detect(Path(path).read_text(encoding="utf-8-sig", errors="replace"))
    except OSError:
        return "any"


def set_mode(path: Path, mode: str) -> None:
    path = Path(path)
    backup = path.with_name(path.name + ".backup")
    current = mode_of(path)
    if mode == current:
        return
    if mode == "none":
        if current == "loaded" and path.exists():
            backup.unlink(missing_ok=True)
            path.replace(backup)
        path.write_text(MARKER + "\n", encoding="utf-8")
    elif mode == "any":
        if current == "loaded" and path.exists():
            backup.unlink(missing_ok=True)
            path.replace(backup)
        path.write_text("", encoding="utf-8")
    elif mode == "loaded":
        if not backup.exists():
            raise IpsetError("нет сохранённого списка")
        path.unlink(missing_ok=True)
        backup.replace(path)
    else:
        raise IpsetError("неизвестный режим")


def apply_download(path: Path, content: str, previous_mode: str) -> str:
    path = Path(path)
    backup = path.with_name(path.name + ".backup")
    path.parent.mkdir(parents=True, exist_ok=True)
    if previous_mode == "loaded":
        path.write_text(content, encoding="utf-8")
        return "loaded"
    backup.write_text(content, encoding="utf-8")
    path.write_text(MARKER + "\n" if previous_mode == "none" else "", encoding="utf-8")
    return previous_mode


def update_from_remote(path: Path, url: str = REMOTE_URL) -> str:
    import httpx

    previous = mode_of(path)
    with httpx.Client(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "Z-GUI"},
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        content = response.text
    if not content.strip():
        raise IpsetError("пустой список")
    return apply_download(path, content, previous)
