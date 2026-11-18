from __future__ import annotations

import sys
import time

from . import ipc


def _ensure_tray(timeout: float = 0.0) -> bool:
    from .command import spawn

    if ipc.ping():
        return True
    spawn("--tray")
    if timeout <= 0:
        return False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if ipc.ping(timeout=0.5):
            return True
        time.sleep(0.1)
    return False


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--smoke-proxy" in args:
        index = args.index("--smoke-proxy")
        if index + 1 >= len(args):
            return 1
        from .core.bridge import smoke

        return smoke(args[index + 1])
    if "--ui-demo" in args:
        from .ui.window import run_window

        return run_window(demo=True)
    if "--tray" in args:
        from .tray import TrayApp

        return TrayApp().run()
    if "--window" not in args:
        _ensure_tray()
    from .ui.window import run_window

    return run_window()


if __name__ == "__main__":
    raise SystemExit(main())
