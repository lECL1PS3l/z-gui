from __future__ import annotations

from PySide6.QtCore import Property, QObject, Slot, Signal


def _rows(*items: tuple[str, str]) -> list[dict]:
    return [{"name": name, "detail": detail, "id": name} for name, detail in items]


BASE = {
    "version": "Версия 1.0.0",
    "zapretOn": False,
    "bridgeOn": False,
    "applyLabel": "Применить",
    "gameFilter": False,
    "autostart": True,
    "rows": [],
    "selected": 0,
    "phase": "idle",
    "testName": "",
    "testCount": "",
    "testValue": 0.0,
    "updateVisible": False,
    "updateLabel": "",
    "updateProgress": 0.0,
    "updateBusy": False,
    "busy": False,
    "canTest": True,
    "canApply": False,
    "canCancel": False,
    "errorTitle": "",
    "errorReason": "",
    "errorFix": False,
    "errorRestore": False,
    "errorClose": False,
}

SCENARIOS = [
    ("Пусто", {}),
    (
        "Результаты",
        {
            "rows": _rows(
                ("ALT3", "27/30 · 61 мс"),
                ("ALT1", "27/30 · 74 мс"),
                ("general", "19/30 · 58 мс"),
            ),
            "canApply": True,
            "applyLabel": "Применить",
        },
    ),
    (
        "Длинные названия",
        {
            "rows": _rows(
                ("FAKE TLS AUTO ALT3", "40/40 · 1432 мс"),
                ("SIMPLE FAKE ALT2", "40/40 · 987 мс"),
                ("EXP", "40/40 · 1204 мс"),
            ),
            "canApply": True,
            "applyLabel": "Применить",
        },
    ),
    (
        "Включено",
        {
            "zapretOn": True,
            "rows": _rows(
                ("ALT9", "40/40 · 226 мс"),
                ("ALT11", "40/40 · 231 мс"),
                ("EXP", "40/40 · 240 мс"),
            ),
            "applyLabel": "Применена",
        },
    ),
    (
        "Другая стратегия",
        {
            "zapretOn": True,
            "rows": _rows(
                ("ALT9", "40/40 · 226 мс"),
                ("ALT11", "40/40 · 231 мс"),
                ("EXP", "40/40 · 240 мс"),
            ),
            "selected": 1,
            "canApply": True,
            "applyLabel": "Применить",
        },
    ),
    (
        "Выбрана, но выключено",
        {
            "rows": _rows(
                ("ALT9", "40/40 · 226 мс"),
                ("ALT11", "40/40 · 231 мс"),
                ("EXP", "40/40 · 240 мс"),
            ),
            "canApply": True,
            "applyLabel": "Включить",
        },
    ),
    (
        "Применяем",
        {
            "rows": _rows(
                ("ALT9", "40/40 · 226 мс"),
                ("ALT11", "40/40 · 231 мс"),
                ("EXP", "40/40 · 240 мс"),
            ),
            "busy": True,
            "applyLabel": "Применяем…",
        },
    ),
    (
        "Тест: 12 из 22",
        {
            "phase": "test",
            "testName": "FAKE TLS AUTO ALT",
            "testCount": "12 / 22",
            "testValue": 0.55,
            "busy": True,
            "canTest": False,
            "canCancel": True,
        },
    ),
    (
        "Ошибка: все действия",
        {
            "phase": "error",
            "errorTitle": "Не удалось запустить Zapret",
            "errorReason": "Причина: драйвер занят другой программой\nпроверьте конфликтующие программы",
            "errorFix": True,
            "errorRestore": True,
            "errorClose": True,
            "canTest": False,
        },
    ),
    (
        "Ошибка: длинный текст",
        {
            "phase": "error",
            "errorTitle": "Не удалось подобрать стратегию",
            "errorReason": "Причина: ни одна стратегия не прошла проверку на выбранных целях\nпроверьте конфликтующие программы и драйвер",
            "errorClose": True,
            "canTest": False,
        },
    ),
    (
        "Обновление",
        {
            "updateVisible": True,
            "updateLabel": "Обновление · 1.10.5",
        },
    ),
    (
        "Обновление идёт",
        {
            "updateVisible": True,
            "updateBusy": True,
            "updateProgress": 0.62,
            "busy": True,
        },
    ),
    (
        "Всё занято",
        {
            "zapretOn": True,
            "bridgeOn": True,
            "busy": True,
            "rows": _rows(
                ("ALT9", "40/40 · 226 мс"),
                ("ALT11", "40/40 · 231 мс"),
                ("EXP", "40/40 · 240 мс"),
            ),
            "canTest": False,
            "applyLabel": "Применена",
        },
    ),
    (
        "Пусто и занято",
        {
            "busy": True,
            "canTest": False,
            "applyLabel": "Применяем…",
        },
    ),
]


class DemoBackend(QObject):
    changed = Signal()

    demo = Property(bool, lambda self: True, constant=True)
    demoTitle = Property(str, lambda self: self._title, notify=changed)
    version = Property(str, lambda self: self._view["version"], notify=changed)
    zapretOn = Property(bool, lambda self: self._view["zapretOn"], notify=changed)
    bridgeOn = Property(bool, lambda self: self._view["bridgeOn"], notify=changed)
    applyLabel = Property(str, lambda self: self._view["applyLabel"], notify=changed)
    gameFilter = Property(bool, lambda self: self._view["gameFilter"], notify=changed)
    autostart = Property(bool, lambda self: self._view["autostart"], notify=changed)
    rows = Property("QVariantList", lambda self: self._view["rows"], notify=changed)
    selected = Property(int, lambda self: self._view["selected"], notify=changed)
    phase = Property(str, lambda self: self._view["phase"], notify=changed)
    testName = Property(str, lambda self: self._view["testName"], notify=changed)
    testCount = Property(str, lambda self: self._view["testCount"], notify=changed)
    testValue = Property(float, lambda self: self._view["testValue"], notify=changed)
    updateVisible = Property(bool, lambda self: self._view["updateVisible"], notify=changed)
    updateLabel = Property(str, lambda self: self._view["updateLabel"], notify=changed)
    updateProgress = Property(float, lambda self: self._view["updateProgress"], notify=changed)
    updateBusy = Property(bool, lambda self: self._view["updateBusy"], notify=changed)
    busy = Property(bool, lambda self: self._view["busy"], notify=changed)
    canTest = Property(bool, lambda self: self._view["canTest"], notify=changed)
    canApply = Property(bool, lambda self: self._view["canApply"], notify=changed)
    canCancel = Property(bool, lambda self: self._view["canCancel"], notify=changed)
    errorTitle = Property(str, lambda self: self._view["errorTitle"], notify=changed)
    errorReason = Property(str, lambda self: self._view["errorReason"], notify=changed)
    errorFix = Property(bool, lambda self: self._view["errorFix"], notify=changed)
    errorRestore = Property(bool, lambda self: self._view["errorRestore"], notify=changed)
    errorClose = Property(bool, lambda self: self._view["errorClose"], notify=changed)

    def __init__(self) -> None:
        super().__init__()
        self._index = 0
        self._title = ""
        self._view = dict(BASE)
        self._select(0)

    def _select(self, index: int) -> None:
        self._index = index % len(SCENARIOS)
        name, overrides = SCENARIOS[self._index]
        self._view = dict(BASE)
        self._view.update(overrides)
        self._title = f"Z-GUI — демо {self._index + 1}/{len(SCENARIOS)}: {name} · ← →"
        self.changed.emit()

    @Slot()
    def demoNext(self) -> None:
        self._select(self._index + 1)

    @Slot()
    def demoPrev(self) -> None:
        self._select(self._index - 1)

    @Slot()
    def toggleZapret(self) -> None:
        pass

    @Slot()
    def toggleBridge(self) -> None:
        pass

    @Slot()
    def startTest(self) -> None:
        pass

    @Slot()
    def cancelTest(self) -> None:
        pass

    @Slot()
    def applyStrategy(self) -> None:
        pass

    @Slot()
    def fixError(self) -> None:
        pass

    @Slot()
    def restoreTools(self) -> None:
        pass

    @Slot()
    def dismissError(self) -> None:
        pass

    @Slot()
    def updateNow(self) -> None:
        pass

    @Slot()
    def updateLater(self) -> None:
        pass

    @Slot(bool)
    def setGameFilter(self, value: bool) -> None:
        pass

    @Slot(bool)
    def setAutostart(self, value: bool) -> None:
        pass

    @Slot(int)
    def selectRow(self, index: int) -> None:
        pass

    @Slot(int, int)
    def saveWindowPos(self, x: int, y: int) -> None:
        pass

    def shutdown(self) -> None:
        pass
