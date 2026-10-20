from __future__ import annotations

NOOP = "noop"
ENABLE = "enable"
APPLY = "apply"


def decision(selected: str, current: str, enabled: bool) -> str:
    if not selected:
        return NOOP
    if selected != current:
        return APPLY
    return NOOP if enabled else ENABLE
