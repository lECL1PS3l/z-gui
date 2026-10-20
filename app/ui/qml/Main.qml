import QtQuick

Window {
    id: root
    width: 420
    height: 320
    minimumWidth: 420
    maximumWidth: 420
    minimumHeight: 320
    maximumHeight: 320
    visible: true
    title: backend.demo ? backend.demoTitle : "Z-GUI"
    color: "#17181C"
    flags: Qt.Window | Qt.WindowTitleHint | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint

    readonly property color cardColor: "#23252B"
    readonly property color cardBorder: "#2F323A"
    readonly property color textMain: "#EDEEF2"
    readonly property color textMuted: "#9AA0AC"
    readonly property color textDim: "#6C727E"
    readonly property color accent: "#3399FF"
    readonly property color warn: "#F2B544"
    readonly property string uiFont: "Segoe UI"

    Column {
        id: layout
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        Row {
            width: layout.width
            height: 56
            spacing: 12

            Rectangle {
                width: (layout.width - 12) / 2
                height: 56
                radius: 12
                color: root.cardColor
                border.width: 1
                border.color: root.cardBorder

                Text {
                    x: 14
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Zapret"
                    color: root.textMuted
                    font.family: root.uiFont
                    font.pixelSize: 12
                    font.weight: 600
                }

                Toggle {
                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    checked: backend.zapretOn
                    interactive: !backend.busy && backend.phase !== "test"
                    onToggled: backend.toggleZapret()
                }
            }

            Rectangle {
                width: (layout.width - 12) / 2
                height: 56
                radius: 12
                color: root.cardColor
                border.width: 1
                border.color: root.cardBorder

                Text {
                    x: 14
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Telegram"
                    color: root.textMuted
                    font.family: root.uiFont
                    font.pixelSize: 12
                    font.weight: 600
                }

                Toggle {
                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    checked: backend.bridgeOn
                    interactive: !backend.busy && backend.phase !== "test"
                    onToggled: backend.toggleBridge()
                }
            }
        }

        Row {
            width: layout.width
            height: 24

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "Game Filter"
                color: root.textMain
                font.family: root.uiFont
                font.pixelSize: 12
            }

            Check {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                checked: backend.gameFilter
                interactive: !backend.busy && backend.phase !== "test"
                onToggled: backend.setGameFilter(!backend.gameFilter)
            }
        }

        Rectangle {
            width: layout.width
            height: 112
            radius: 12
            color: root.cardColor
            border.width: 1
            border.color: root.cardBorder

            Column {
                visible: backend.phase === "idle"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.topMargin: 8

                Repeater {
                    model: backend.rows

                    StrategyRow {
                        width: layout.width
                        height: 20
                        name: modelData.name
                        detail: modelData.detail
                        selected: index === backend.selected
                        onPicked: backend.selectRow(index)
                    }
                }
            }

            SlimButton {
                visible: backend.phase === "idle"
                x: 12
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 8
                text: "Тест"
                active: backend.canTest
                onClicked: backend.startTest()
            }

            SlimButton {
                visible: backend.phase === "idle"
                anchors.right: parent.right
                anchors.rightMargin: 12
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 8
                text: backend.applyLabel

                active: backend.canApply
                onClicked: backend.applyStrategy()
            }

            Column {
                visible: backend.phase === "test"
                anchors.fill: parent
                anchors.margins: 12
                spacing: 6

                Text {
                    width: parent.width
                    text: backend.testName.length > 0 ? backend.testName : "Подготовка"
                    color: root.textMain
                    elide: Text.ElideRight
                    font.family: root.uiFont
                    font.pixelSize: 12
                    font.weight: 600
                }

                Rectangle {
                    width: parent.width
                    height: 6
                    radius: 3
                    color: root.cardBorder

                    Rectangle {
                        width: parent.width * backend.testValue
                        height: 6
                        radius: 3
                        color: root.accent
                    }
                }

                Text {
                    text: backend.testCount
                    color: root.textMuted
                    font.family: root.uiFont
                    font.pixelSize: 11
                }

                SlimButton {
                    text: "Отмена"
                    active: backend.canCancel
                    onClicked: backend.cancelTest()
                }
            }

            Item {
                visible: backend.phase === "error"
                anchors.fill: parent
                anchors.margins: 12

                Text {
                    id: errorTitle
                    width: parent.width
                    text: backend.errorTitle
                    color: root.warn
                    elide: Text.ElideRight
                    font.family: root.uiFont
                    font.pixelSize: 12
                    font.weight: 600
                }

                Text {
                    anchors.top: errorTitle.bottom
                    anchors.topMargin: 6
                    width: parent.width
                    text: backend.errorReason
                    color: root.textMuted
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                    lineHeight: 1.1
                    font.family: root.uiFont
                    font.pixelSize: 11
                }

                Row {
                    anchors.left: parent.left
                    anchors.bottom: parent.bottom
                    spacing: 8

                    SlimButton {
                        visible: backend.errorFix
                        text: "Исправить"
                        onClicked: backend.fixError()
                    }

                    SlimButton {
                        visible: backend.errorRestore
                        text: "Восстановить"
                        onClicked: backend.restoreTools()
                    }

                    SlimButton {
                        visible: backend.errorClose
                        text: "Закрыть"
                        onClicked: backend.dismissError()
                    }
                }
            }
        }

        Row {
            width: layout.width
            height: 24

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "Запускать с Windows"
                color: root.textMain
                font.family: root.uiFont
                font.pixelSize: 12
            }

            Check {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                checked: backend.autostart
                interactive: !backend.updateBusy
                onToggled: backend.setAutostart(!backend.autostart)
            }
        }

        Item {
            width: layout.width
            height: 24

            Text {
                visible: !backend.updateVisible
                anchors.verticalCenter: parent.verticalCenter
                text: backend.version
                color: root.textMuted
                font.family: root.uiFont
                font.pixelSize: 11
            }

            Row {
                visible: backend.updateVisible && !backend.updateBusy
                anchors.fill: parent
                spacing: 8

                Text {
                    width: parent.width - 140
                    anchors.verticalCenter: parent.verticalCenter
                    text: backend.updateLabel
                    color: root.textMain
                    elide: Text.ElideRight
                    font.family: root.uiFont
                    font.pixelSize: 12
                }

                SlimButton {
                    small: true
                    text: "Да"
                    onClicked: backend.updateNow()
                }

                SlimButton {
                    small: true
                    text: "Позже"
                    onClicked: backend.updateLater()
                }
            }

            Row {
                visible: backend.updateVisible && backend.updateBusy
                anchors.fill: parent
                spacing: 8

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Обновляем…"
                    color: root.textMain
                    font.family: root.uiFont
                    font.pixelSize: 12
                }

                Rectangle {
                    width: parent.width - 150
                    height: 6
                    radius: 3
                    anchors.verticalCenter: parent.verticalCenter
                    color: root.cardBorder

                    Rectangle {
                        width: parent.width * backend.updateProgress
                        height: 6
                        radius: 3
                        color: root.accent
                    }
                }

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: Math.round(backend.updateProgress * 100) + " %"
                    color: root.textMuted
                    font.family: root.uiFont
                    font.pixelSize: 11
                }
            }
        }
    }

    Item {
        id: demoKeys
        anchors.fill: parent
        focus: backend.demo
        Keys.onRightPressed: backend.demoNext()
        Keys.onLeftPressed: backend.demoPrev()
        Keys.onEscapePressed: Qt.quit()

        Component.onCompleted: {
            if (backend.demo) {
                demoKeys.forceActiveFocus()
            }
        }
    }

    onActiveChanged: {
        if (active && backend.demo) {
            demoKeys.forceActiveFocus()
        }
    }
}
