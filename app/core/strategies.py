from __future__ import annotations

import re
from pathlib import Path

DEFAULT = "general.bat"


def list_files(root: Path) -> list[Path]:
    root = Path(root)
    files = [path for path in root.glob("general*.bat") if path.is_file()]
    files.sort(key=lambda path: (path.name.lower() != DEFAULT, path.name.lower()))
    return files


def names(root: Path) -> list[str]:
    return [path.name for path in list_files(root)]


def label(name: str) -> str:
    stem = Path(name).stem
    if stem.lower() == "general":
        return "general"
    match = re.match(r"general\s*\((.*)\)$", stem, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return stem


def pick(root: Path, wanted: str | None) -> str:
    available = names(root)
    if not available:
        return DEFAULT
    if wanted and wanted in available:
        return wanted
    if DEFAULT in available:
        return DEFAULT
    return available[0]
