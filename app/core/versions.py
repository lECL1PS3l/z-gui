from __future__ import annotations

import re
from datetime import datetime, timezone


def parse_version(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    cleaned = str(value).strip().lstrip("vV")
    parts = re.split(r"[._\-+]", cleaned)
    result: list[int] = []
    for part in parts:
        match = re.match(r"(\d+)", part)
        if not match:
            break
        result.append(int(match.group(1)))
    return tuple(result)


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_newer(remote: str | None, remote_date: str | None, local: str | None, local_date: str | None) -> bool:
    remote_version = parse_version(remote)
    local_version = parse_version(local)
    if not remote_version:
        return False
    if remote_version > local_version:
        return True
    if remote_version < local_version:
        return False
    if not local:
        return True
    remote_parsed = parse_date(remote_date)
    local_parsed = parse_date(local_date)
    if remote_parsed and local_parsed:
        return remote_parsed > local_parsed
    return False
