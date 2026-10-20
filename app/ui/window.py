from __future__ import annotations

import sys

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from .. import paths, winapi
from ..core import bootstrap
from ..core.locks import FileLock
from ..core.state import StateStore
from ..logs import get_logger
from .backend import Backend
from .demo import DemoBackend

log = get_logger("z-gui.window")
WINDOW_WIDTH = 420
WINDOW_HEIGHT = 320


def run_window(demo: bool = False) -> int:
    if demo:
        return _run(demo=True)
    lock = FileLock(paths.window_lock_path())
    if not lock.acquire(timeout=0):
        winapi.show_window(winapi.find_window("Z-GUI"))
        return 0
    try:
        return _run()
    finally:
        lock.release()


def _run(demo: bool = False) -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Z-GUI")
    app.setQuitOnLastWindowClosed(True)
    if paths.icon_path().exists():
        app.setWindowIcon(QIcon(str(paths.icon_path())))
    store = None
    if demo:
        backend = DemoBackend()
    else:
        bootstrap.ensure_ready()
        store = StateStore(paths.state_path())
        backend = Backend(store)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(str(paths.qml_dir() / "Main.qml")))
    objects = engine.rootObjects()
    if not objects:
        log.warning("не удалось загрузить интерфейс")
        return 1
    window = objects[0]

    def place() -> None:
        screen = QGuiApplication.primaryScreen()
        geometry = screen.availableGeometry() if screen is not None else None
        if geometry is not None and store is None:
            window.setPosition(
                geometry.center().x() - WINDOW_WIDTH // 2,
                geometry.center().y() - WINDOW_HEIGHT // 2,
            )
            return
        if store is None:
            return
        data = store.read()
        saved = data.get("window")
        if isinstance(saved, list) and len(saved) == 2 and geometry is not None:
            x = int(saved[0])
            y = int(saved[1])
            if (
                geometry.left() <= x <= geometry.right() - WINDOW_WIDTH
                and geometry.top() <= y <= geometry.bottom() - WINDOW_HEIGHT
            ):
                window.setPosition(x, y)
                return
        if geometry is not None:
            window.setPosition(
                geometry.center().x() - WINDOW_WIDTH // 2,
                geometry.center().y() - WINDOW_HEIGHT // 2,
            )

    def save() -> None:
        if store is None:
            return
        backend.saveWindowPos(window.x(), window.y())
        backend.shutdown()

    QTimer.singleShot(0, place)
    QTimer.singleShot(60, lambda: winapi.dark_title(int(window.winId())))
    app.aboutToQuit.connect(save)
    return app.exec()
