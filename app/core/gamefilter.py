from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_RANGE = "1024-65535"
ITEM_RE = re.compile(r"^(?:[1-9][0-9]{0,4})(?:-(?:[1-9][0-9]{0,4}))?$")


@dataclass(frozen=True)
class GameFilter:
    mode: str = "disabled"
    tcp: str = DEFAULT_RANGE
    udp: str = DEFAULT_RANGE

    @property
    def tcp_value(self) -> str:
        if self.mode in ("all", "tcp"):
            return self.tcp
        return "12"

    @property
    def udp_value(self) -> str:
        if self.mode in ("all", "udp"):
            return self.udp
        return "12"

    @property
    def enabled(self) -> bool:
        return self.mode in ("all", "tcp", "udp")


def valid_range(value: str) -> str | None:
    cleaned = (value or "").replace(" ", "")
    if not cleaned:
        return None
    for item in cleaned.split(","):
        if not ITEM_RE.match(item):
            return None
        parts = item.split("-")
        start = int(parts[0])
        end = int(parts[1]) if len(parts) > 1 else start
        if start > 65535 or end > 65535 or start > end:
            return None
    return cleaned


def parse_text(text: str) -> GameFilter:
    mode = "disabled"
    tcp_range = DEFAULT_RANGE
    udp_range = DEFAULT_RANGE
    tcp_candidate = ""
    udp_candidate = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if "=" in line:
            key, value = line.split("=", 1)
        else:
            key, value = line, ""
        key = key.strip().lower()
        value = value.strip()
        if key == "mode":
            mode = value.lower()
        elif key == "all":
            mode = "all"
        elif key == "udp":
            if value == "":
                mode = "udp"
            else:
                udp_candidate = value
        elif key == "tcp":
            if value == "":
                mode = "tcp"
            else:
                tcp_candidate = value
    checked = valid_range(tcp_candidate)
    if checked:
        tcp_range = checked
    checked = valid_range(udp_candidate)
    if checked:
        udp_range = checked
    if mode not in ("all", "tcp", "udp"):
        mode = "disabled"
    return GameFilter(mode=mode, tcp=tcp_range, udp=udp_range)


def parse_file(path: Path) -> GameFilter:
    try:
        text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return GameFilter()
    return parse_text(text)


def render(game: GameFilter, mode: str | None = None) -> str:
    chosen = mode or game.mode
    return f"mode={chosen}\ntcp={game.tcp}\nudp={game.udp}\n"


def write_mode(path: Path, game: GameFilter, enabled: bool) -> GameFilter:
    updated = GameFilter(mode="all" if enabled else "disabled", tcp=game.tcp, udp=game.udp)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(render(updated), encoding="utf-8")
    return updated
