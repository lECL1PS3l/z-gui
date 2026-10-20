import QtQuick

Rectangle {
    id: root
    property bool checked: false
    property bool interactive: true
    signal toggled()

    width: 18
    height: 18
    radius: 5
    color: root.checked ? "#3399FF" : "transparent"
    border.width: 1.5
    border.color: root.checked ? "#3399FF" : (root.interactive ? "#6C727E" : "#3A3D46")

    Text {
        anchors.centerIn: parent
        text: "✓"
        visible: root.checked
        color: "#101114"
        font.family: "Segoe UI"
        font.pixelSize: 12
        font.weight: 700
    }

    MouseArea {
        anchors.fill: parent
        enabled: root.interactive
        cursorShape: Qt.PointingHandCursor
        onClicked: root.toggled()
    }
}
