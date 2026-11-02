import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Commons as Commons
import qs.Ui

Panel {
  id: root
  moduleName: "commandcode.usage"
  ipcTarget: "commandcode.usage"
  manageIpc: false

  readonly property color foreground: bar ? bar.foreground : Commons.Color.foreground
  readonly property color urgent: bar ? bar.urgent : Commons.Color.urgent
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property color track: Style.selectedFillFor(foreground, Commons.Color.accent)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  property var limits: []
  property string planName: ""
  property string errorText: ""
  property bool ready: false
  property bool checked: false
  property bool promptForKey: false
  property string pendingKey: ""
  property double nowMs: Date.now()
  property double lastFetchMs: 0

  readonly property bool alarming: {
    for (var i = 0; i < limits.length; i++)
      if (Number(limits[i].percent) >= 0.9) return true
    return false
  }

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)) }
  function alpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

  function scriptPath() {
    return decodeURIComponent(Qt.resolvedUrl("usage.py").toString().replace(/^file:\/\//, ""))
  }

  function refreshNow(force) {
    var now = Date.now()
    if (fetch.running) return
    if (!force && now - lastFetchMs < 20000) return
    lastFetchMs = now
    fetch.running = true
  }

  function acceptLine(data) {
    var text = String(data || "").trim()
    if (text === "" || text.charAt(0) !== "{") return
    var parsed
    try {
      parsed = JSON.parse(text)
    } catch (e) {
      return
    }
    checked = true
    if (parsed && parsed.ok && parsed.limits instanceof Array) {
      limits = parsed.limits
      planName = String(parsed.planName || "Subscription")
      errorText = ""
      ready = true
      promptForKey = false
      pendingKey = ""
      keyField.text = ""
      nowMs = Date.now()
      return
    }
    errorText = parsed && parsed.error ? String(parsed.error) : "Couldn't read Command Code usage."
    promptForKey = !!(parsed && parsed.needsKey)
    if (!ready) limits = []
  }

  function saveKey() {
    if (store.running || fetch.running) return
    var value = keyField.text.trim()
    if (value.length < 20 || value.indexOf(" ") !== -1) {
      checked = true
      promptForKey = true
      errorText = "Paste the API key from Command Code Studio. It is one line, with no spaces."
      return
    }
    pendingKey = value
    keyField.text = ""
    store.running = true
  }

  function openStudio() {
    browser.exec(["xdg-open", "https://commandcode.ai/studio/"])
  }

  function resetMs(limit) {
    if (!limit || !limit.resetsAt) return -1
    var ms = new Date(String(limit.resetsAt)).getTime()
    return isFinite(ms) ? ms - nowMs : -1
  }

  function formatDuration(ms) {
    if (!(ms > 0)) return "now"
    var minutes = Math.floor(ms / 60000)
    var hours = Math.floor(minutes / 60)
    var days = Math.floor(hours / 24)
    if (days > 0) return days + "d " + (hours % 24) + "h"
    if (hours > 0) return hours + "h " + (minutes % 60) + "m"
    return Math.max(1, minutes) + "m"
  }

  function resetLabel(limit) {
    var remaining = resetMs(limit)
    if (!(remaining > 0)) return remaining === -1 ? "" : "Resets now"
    if (limit.resetStyle === "date") {
      var when = new Date(String(limit.resetsAt))
      var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
      return "Resets on " + months[when.getMonth()] + " " + when.getDate()
    }
    return "Resets in " + formatDuration(remaining)
  }

  visible: true
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onPromptForKeyChanged: {
    if (promptForKey && opened)
      Qt.callLater(function() { keyField.forceActiveFocus() })
  }

  onOpenedChanged: {
    if (!opened) {
      pendingKey = ""
      keyField.text = ""
      return
    }
    nowMs = Date.now()
    refreshNow(true)
    Qt.callLater(function() {
      if (promptForKey) keyField.forceActiveFocus()
      else keyCatcher.forceActiveFocus()
    })
  }

  Component.onCompleted: refreshNow(true)

  Timer {
    interval: Math.max(60, Number(root.setting("refreshIntervalSec", 300))) * 1000
    running: true
    repeat: true
    onTriggered: root.refreshNow(false)
  }

  Timer {
    interval: 30000
    running: root.opened
    repeat: true
    onTriggered: root.nowMs = Date.now()
  }

  Process {
    id: fetch
    command: ["/usr/bin/python3", "-B", "-s", "-u", root.scriptPath()]
    stdout: SplitParser { onRead: function(data) { root.acceptLine(data) } }
    stderr: SplitParser {
      onRead: function(data) {
        var message = String(data || "").trim()
        if (message !== "") console.warn("Command Code usage:", message)
      }
    }
  }

  // The key travels on stdin, never on the command line.
  Process {
    id: store
    stdinEnabled: true
    command: ["/usr/bin/python3", "-B", "-s", "-u", root.scriptPath(), "--store-key"]
    stdout: SplitParser { onRead: function(data) { root.acceptLine(data) } }
    stderr: SplitParser {
      onRead: function(data) {
        var message = String(data || "").trim()
        if (message !== "") console.warn("Command Code usage:", message)
      }
    }
    onStarted: {
      write(root.pendingKey + "\n")
      root.pendingKey = ""
    }
  }

  Process {
    id: browser
  }

  IpcHandler {
    target: root.ipcTarget
    function open(): void { root.open() }
    function close(): void { root.close() }
    function show(): void { root.open() }
    function hide(): void { root.close() }
    function toggle(): void { root.toggle() }
    function refresh(): string { root.refreshNow(true); return "ok" }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "⌘"
    active: root.alarming
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.MiddleButton) root.refreshNow(true)
      else root.toggle()
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(380))
    contentHeight: panel.fittedContentHeight(column.implicitHeight, Style.space(420))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      blocked: keyField.activeFocus
      onActivateRequested: root.refreshNow(true)
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(t) { if (t === "r" || t === "R") root.refreshNow(true) }

      Column {
        id: column
        width: parent.width
        spacing: Style.space(12)

        PanelHero {
          width: parent.width
          title: "Command Code"
          meta: !root.checked ? "Checking" : (root.promptForKey ? "Setup" : (root.planName || "Subscription"))
          foreground: root.foreground
          fontFamily: root.fontFamily

          iconComponent: Component {
            Text {
              text: "⌘"
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.display
            }
          }
        }

        BorderSurface {
          visible: root.errorText !== ""
          width: parent.width
          implicitHeight: statusText.implicitHeight + Style.spacing.xl * 2
          color: root.alpha(root.urgent, 0.10)
          borderSpec: Border.flat(root.alpha(root.urgent, 0.35), 1)
          radius: Style.cornerRadius

          Text {
            id: statusText
            textFormat: Text.PlainText
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: Style.space(12)
            anchors.rightMargin: Style.space(12)
            text: root.errorText
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
          }
        }

        Column {
          id: setupSection
          visible: root.promptForKey
          width: parent.width
          spacing: Style.space(8)

          Text {
            textFormat: Text.PlainText
            width: parent.width
            wrapMode: Text.WordWrap
            text: "Paste an API key from Command Code Studio. It is saved on this computer in ~/.commandcode/auth.json and is not written into the bar settings."
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }

          Button {
            text: "Open Studio"
            bordered: true
            foreground: root.foreground
            onClicked: root.openStudio()
          }

          TextField {
            id: keyField
            width: parent.width
            password: true
            placeholderText: "API key"
            foreground: root.foreground
            enabled: !store.running
            onAccepted: root.saveKey()
          }

          Button {
            text: store.running ? "Saving" : "Save key"
            bordered: true
            foreground: root.foreground
            onClicked: root.saveKey()
          }
        }

        PanelSeparator {
          visible: limitsSection.visible
          foreground: root.foreground
        }

        Column {
          id: limitsSection
          visible: root.limits.length > 0
          width: parent.width
          spacing: Style.space(10)

          PanelSectionHeader {
            text: "LIMITS"
            foreground: root.foreground
            fontFamily: root.fontFamily
          }

          Repeater {
            model: root.limits

            LimitRow {
              required property var modelData
              width: limitsSection.width
              window: modelData
            }
          }
        }
      }
    }
  }

  component LimitRow: Column {
    id: limitRow
    property var window: null
    readonly property bool rowAlarm: window && Number(window.percent) >= 0.9

    spacing: Style.space(6)

    Item {
      width: parent.width
      implicitHeight: Math.max(limitLabel.implicitHeight, limitValue.implicitHeight)

      Text {
        id: limitLabel
        textFormat: Text.PlainText
        text: limitRow.window ? String(limitRow.window.title || "") : ""
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        elide: Text.ElideRight
        anchors.left: parent.left
        anchors.right: limitValue.left
        anchors.rightMargin: Style.spacing.sm
        anchors.verticalCenter: parent.verticalCenter
      }

      Text {
        id: limitValue
        textFormat: Text.PlainText
        text: limitRow.window && Number(limitRow.window.percent) >= 0
          ? Math.round(Number(limitRow.window.percent) * 100) + "%"
          : "—"
        color: limitRow.rowAlarm ? root.urgent : root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
      }
    }

    Item {
      width: parent.width
      implicitHeight: Math.max(Style.space(4), Math.round(Style.spacing.controlHeight * 0.14))

      Rectangle {
        id: meterTrack
        anchors.fill: parent
        radius: height / 2
        color: root.track
      }

      Rectangle {
        anchors.left: meterTrack.left
        anchors.verticalCenter: meterTrack.verticalCenter
        height: meterTrack.height
        radius: meterTrack.radius
        width: meterTrack.width * root.clamp(limitRow.window ? Number(limitRow.window.percent) : 0, 0, 1)
        color: limitRow.rowAlarm ? root.urgent : root.foreground

        Behavior on width {
          NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
        }
      }
    }

    Text {
      textFormat: Text.PlainText
      width: parent.width
      text: root.resetLabel(limitRow.window)
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
    }
  }
}
