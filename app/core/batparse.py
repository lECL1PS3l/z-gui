from __future__ import annotations

import re
from pathlib import Path

VAR_RE = re.compile(r"%([^%\s]+)%")


class BatParseError(ValueError):
    pass


def split_windows_args(text: str) -> list[str]:
    result: list[str] = []
    index = 0
    length = len(text)
    while True:
        while index < length and text[index] in " \t":
            index += 1
        if index >= length:
            break
        current: list[str] = []
        quoted = False
        while index < length:
            char = text[index]
            if char == "\\":
                start = index
                while index < length and text[index] == "\\":
                    index += 1
                count = index - start
                if index < length and text[index] == '"':
                    current.append("\\" * (count // 2))
                    if count % 2:
                        current.append('"')
                        index += 1
                    else:
                        quoted = not quoted
                        index += 1
                else:
                    current.append("\\" * count)
            elif char == '"':
                quoted = not quoted
                index += 1
            elif not quoted and char in " \t":
                break
            else:
                current.append(char)
                index += 1
        result.append("".join(current))
    return result


def logical_lines(text: str) -> list[str]:
    result: list[str] = []
    buffer = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        buffer += line
        if buffer.endswith("^"):
            buffer = buffer[:-1]
            continue
        full = buffer
        buffer = ""
        stripped = full.strip()
        if not stripped:
            continue
        if stripped.startswith("::"):
            continue
        lowered = stripped.lower()
        if lowered.startswith("rem ") or lowered == "rem":
            continue
        result.append(full)
    if buffer.strip():
        result.append(buffer)
    return result


def substitute(text: str, variables: dict[str, str]) -> str:
    lookup = {key.upper(): value for key, value in variables.items()}

    def replace(match: re.Match[str]) -> str:
        key = match.group(1).upper()
        return lookup.get(key, "")

    return VAR_RE.sub(replace, text)


def extract_argv(
    text: str,
    base_dir: Path,
    bin_dir: Path,
    lists_dir: Path,
    game_tcp: str,
    game_udp: str,
) -> list[str]:
    base = str(base_dir)
    if not base.endswith("\\"):
        base += "\\"
    bindir = str(bin_dir)
    if not bindir.endswith("\\"):
        bindir += "\\"
    lists = str(lists_dir)
    if not lists.endswith("\\"):
        lists += "\\"
    variables = {
        "~dp0": base,
        "BIN": bindir,
        "LISTS": lists,
        "GameFilterTCP": game_tcp,
        "GameFilterUDP": game_udp,
        "GameFilter": game_tcp,
    }
    for line in logical_lines(text):
        lowered = line.lower()
        position = lowered.find("winws.exe")
        if position < 0:
            continue
        rest = line[position + len("winws.exe"):]
        if rest.startswith('"'):
            rest = rest[1:]
        rest = substitute(rest, variables)
        argv = split_windows_args(rest)
        if not argv:
            raise BatParseError("пустая команда запуска")
        return argv
    raise BatParseError("в файле нет запуска winws.exe")


def parse_file(
    path: Path,
    game_tcp: str = "12",
    game_udp: str = "12",
) -> list[str]:
    text = Path(path).read_text(encoding="utf-8-sig")
    base = Path(path).resolve().parent
    return extract_argv(
        text,
        base_dir=base,
        bin_dir=base / "bin",
        lists_dir=base / "lists",
        game_tcp=game_tcp,
        game_udp=game_udp,
    )
