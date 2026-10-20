import QtQuick

Item {
    id: root
    property bool checked: false
    property bool interactive: true
    signal toggled()

    width: 56
    height: 30

    Rectangle {
        anchors.fill: parent
        radius: 15
        color: root.checked ? "#3399FF" : (root.interactive ? "#3A3D46" : "#2A2C33")

        Behavior on color {
            ColorAnimation { duration: 120 }
        }

        Rectangle {
            id: knob
            width: 24
            height: 24
            radius: 12
            y: 3
            x: root.checked ? 29 : 3
            color: root.checked ? "#101114" : "#9AA0AC"

            Behavior on x {
                NumberAnimation { duration: 120 }
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        enabled: root.interactive
        cursorShape: Qt.PointingHandCursor
        onClicked: root.toggled()
    }
}
