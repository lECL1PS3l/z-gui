import QtQuick

Item {
    id: root
    property string name: ""
    property string detail: ""
    property bool selected: false
    signal picked()

    Rectangle {
        id: dot
        x: 14
        anchors.verticalCenter: parent.verticalCenter
        width: 12
        height: 12
        radius: 6
        color: "transparent"
        border.width: 1
        border.color: root.selected ? "#3399FF" : "#6C727E"

        Rectangle {
            anchors.centerIn: parent
            width: 6
            height: 6
            radius: 3
            color: "#3399FF"
            visible: root.selected
        }
    }

    Text {
        id: nameText
        anchors.left: dot.right
        anchors.leftMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        text: root.name
        color: root.name === "—" ? "#6C727E" : "#EDEEF2"
        font.family: "Segoe UI"
        font.pixelSize: 12
    }

    Text {
        anchors.right: parent.right
        anchors.rightMargin: 14
        anchors.verticalCenter: parent.verticalCenter
        text: root.detail
        color: root.detail === "проверка не выполнялась" ? "#6C727E" : "#9AA0AC"
        font.family: "Segoe UI"
        font.pixelSize: 11
    }

    MouseArea {
        anchors.fill: parent
        enabled: root.name !== "—"
        cursorShape: Qt.PointingHandCursor
        onClicked: root.picked()
    }
}
