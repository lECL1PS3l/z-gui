import QtQuick

Rectangle {
    id: root
    property string text: ""
    property bool active: true
    property bool small: false
    signal clicked()

    width: implicitWidth
    height: implicitHeight
    implicitWidth: Math.max(label.implicitWidth + (small ? 20 : 26), small ? 54 : 72)
    implicitHeight: small ? 24 : 30
    radius: 10
    color: root.active ? (mouse.containsMouse ? "#343842" : "#2B2E36") : "#24262C"
    border.width: 1
    border.color: root.active ? "#3A3E47" : "#2A2C33"

    Behavior on color {
        ColorAnimation { duration: 100 }
    }

    Text {
        id: label
        anchors.centerIn: parent
        text: root.text
        color: root.active ? "#EDEEF2" : "#6C727E"
        font.family: "Segoe UI"
        font.pixelSize: root.small ? 11 : 12
        font.weight: 600
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        enabled: root.active
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
