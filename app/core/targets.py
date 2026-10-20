from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

LINE_RE = re.compile(r'^([A-Za-z0-9_]+)\s*=\s*"(.*)"\s*$')


@dataclass(frozen=True)
class Target:
    name: str
    url: str | None = None
    ping: str | None = None


def parse(text: str) -> list[Target]:
    result: list[Target] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = LINE_RE.match(line)
        if not match:
            continue
        key = match.group(1)
        value = match.group(2).strip()
        if not value:
            continue
        if value.upper().startswith("PING:"):
            host = value[5:].strip()
            if host:
                result.append(Target(name=key, ping=host))
        elif value.startswith("http://") or value.startswith("https://"):
            result.append(Target(name=key, url=value))
    return result


def parse_file(path: Path) -> list[Target]:
    try:
        text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return []
    return parse(text)
