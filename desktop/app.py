"""Apple Settings-inspired native interface, using Windows fonts and controls."""
import sys

from PySide6.QtCore import Qt, QLockFile, QTimer
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QKeySequenceEdit,
    QLineEdit, QListWidget, QMainWindow, QMenu, QMessageBox, QPushButton,
    QScrollArea, QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from config import config
from .controller import DesktopController
from .hotkey import GlobalHotkey
from .settings import DesktopSettings
from .overlay import ActivityOverlay


STYLE = """
* { font-family: 'Segoe UI Variable', 'Segoe UI'; font-size: 14px; color: #202631; }
QMainWindow, QWidget#canvas, QMessageBox { background: #f6f7f9; }
QWidget#sidebar { background: #eceef2; border-right: 1px solid #dfe3ea; }
QLabel { background: transparent; border: none; }
QLabel#brand { font-size: 23px; font-weight: 700; letter-spacing: 3px; }
QLabel#title { font-size: 28px; font-weight: 650; }
QLabel#heroTitle { font-size: 27px; font-weight: 600; }
QLabel#muted { color: #697384; font-size: 13px; }
QLabel#section { color: #647084; font-size: 11px; font-weight: 700; letter-spacing: 1px; }
QLabel#status { color: #2662bc; background: #eaf2ff; border-radius: 12px; padding: 5px 12px; }
QFrame#card { background: white; border: 1px solid #e1e5ec; border-radius: 14px; }
QListWidget { border: none; background: transparent; outline: none; padding: 0px; }
QListWidget::item { padding: 12px 14px; margin: 3px 0px; border-radius: 8px; }
QListWidget::item:selected { background: #dce7fa; color: #195cb8; }
QListWidget::item:hover:!selected { background: #e3e6ed; }
QPushButton { background: #eef1f6; border: 1px solid #dce2eb; border-radius: 8px; padding: 10px 16px; font-weight: 600; }
QPushButton:hover { background: #e1e8f3; }
QPushButton:focus, QLineEdit:focus, QKeySequenceEdit:focus { border: 2px solid #76a8f0; }
QPushButton#primary { background: #2876e2; color: white; border: 1px solid #2876e2; }
QPushButton#primary:hover { background: #1e64c6; }
QPushButton#danger { background: #fff0ef; color: #b33d36; border-color: #edcbc7; }
QPushButton:disabled { background: #eef0f3; color: #929aaa; border-color: #e1e5ec; }
QLineEdit, QKeySequenceEdit, QComboBox { background: white; border: 1px solid #d5dce6; border-radius: 8px; padding: 10px; }
QCheckBox { spacing: 12px; padding: 8px 0px; }
QCheckBox::indicator { width: 20px; height: 20px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: #ced5df; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
"""


def label(text, name=None):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    if name:
        widget.setObjectName(name)
    return widget


def card():
    widget = QFrame()
    widget.setObjectName("card")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(12)
    return widget, layout


def app_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#2876e2"))
    painter.drawRoundedRect(2, 2, 60, 60, 18, 18)
    painter.setPen(QColor("white"))
    font = painter.font()
    font.setPixelSize(34)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Z")
    painter.end()
    return QIcon(pixmap)


class VoiceMark(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(108, 94)
        self.active = False
        self.setAccessibleName("ZENO voice activity")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#edf3fe"))
        painter.drawEllipse(12, 4, 84, 84)
        painter.setBrush(QColor("#2876e2" if self.active else "#82a9e8"))
        for index, height in enumerate((16, 30, 44, 30, 16)):
            painter.drawRoundedRect(29 + index * 11, 46 - height // 2, 6, height, 3, 3)


class DesktopWindow(QMainWindow):
    def __init__(self, application, settings, settings_path, controller=None):
        super().__init__()
        self.application, self.settings, self.settings_path = application, settings, settings_path
        self.controller = controller or DesktopController(settings)
        self.overlay = ActivityOverlay()
        self.closing = False
        self.approval_id = ""
        self.hotkey = GlobalHotkey(application, self.toggle)
        self.setWindowTitle("ZENO — Desktop assistant")
        self.setWindowIcon(app_icon())
        self.resize(1000, 760)
        self.setMinimumSize(820, 620)
        root = QWidget()
        root.setObjectName("canvas")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(216)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(20, 30, 20, 22)
        side.setSpacing(6)
        side.addWidget(label("ZENO", "brand"))
        side.addWidget(label("Your desktop companion", "muted"))
        side.addSpacing(30)
        self.navigation = QListWidget()
        self.navigation.addItems(["Assistant", "Keyboard shortcut", "Voice & microphone", "About & privacy"])
        self.navigation.setAccessibleName("Settings navigation")
        side.addWidget(self.navigation)
        self.side_status = label("●  Microphone off", "muted")
        side.addWidget(self.side_status)
        side.addWidget(label("Here when you need me.", "muted"))
        layout.addWidget(sidebar)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)
        self.build_assistant()
        self.build_shortcut()
        self.build_voice()
        self.build_about()
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        self.controller.event.connect(self.on_event)
        self.controller.approval.connect(self.on_approval)
        self.controller.idle.connect(self.on_idle)
        self.escape = QShortcut(QKeySequence("Esc"), self)
        self.escape.activated.connect(self.controller.stop)
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip("ZENO — microphone off")
        menu = QMenu()
        menu.addAction("Show ZENO", self.reveal)
        menu.addAction("Start / stop", self.toggle)
        menu.addSeparator()
        menu.addAction("Quit ZENO", self.request_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.reveal() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        if settings.shortcut:
            try:
                self.hotkey.register(settings.shortcut)
                self.shortcut_message.setText("Your shortcut is active system-wide while ZENO is running.")
            except ValueError as exc:
                self.shortcut_message.setText(str(exc))
                self.navigation.setCurrentRow(1)
        self.refresh_shortcut()

    def page(self, title, subtitle):
        page = QWidget()
        page.setObjectName("canvas")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 30, 32, 26)
        layout.setSpacing(16)
        layout.addWidget(label(title, "title"))
        layout.addWidget(label(subtitle, "muted"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        self.pages.addWidget(scroll)
        return layout

    def build_assistant(self):
        page = self.page("Assistant", "A little less friction. A little more focus.")
        hero, body = card()
        self.status = label("Ready", "status")
        body.addWidget(self.status, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.mark = VoiceMark()
        body.addWidget(self.mark, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.hero_title = label("Ready when you are", "heroTitle")
        self.hero_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.addWidget(self.hero_title)
        self.shortcut_hint = label("", "muted")
        self.shortcut_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.addWidget(self.shortcut_hint)
        self.start_button = QPushButton("Start listening")
        self.start_button.setObjectName("primary")
        self.start_button.setMinimumWidth(190)
        self.start_button.clicked.connect(self.toggle)
        body.addWidget(self.start_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        body.addWidget(label("Pause naturally to send your command. Press the same shortcut again to stop.", "muted"))
        page.addWidget(hero)
        conversation, body = card()
        body.addWidget(label("CURRENT CONVERSATION", "section"))
        self.transcript = label("Ask something, or give ZENO a task.")
        self.transcript.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.addWidget(self.transcript)
        self.reply = label("Only the useful reply appears here—not terminal logs.", "muted")
        self.reply.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.addWidget(self.reply)
        self.detail = label("", "muted")
        self.detail.hide()
        body.addWidget(self.detail)
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Or type a request…")
        self.input.setAccessibleName("Type a request")
        self.input.returnPressed.connect(self.send_text)
        self.send = QPushButton("Send")
        self.send.clicked.connect(self.send_text)
        row.addWidget(self.input, 1)
        row.addWidget(self.send)
        body.addLayout(row)
        page.addWidget(conversation)
        self.approval_card, body = card()
        body.addWidget(label("YOUR APPROVAL IS NEEDED", "section"))
        self.approval_prompt = label("")
        body.addWidget(self.approval_prompt)
        buttons = QHBoxLayout()
        self.deny = QPushButton("Cancel action")
        self.allow = QPushButton("Approve action")
        self.allow.setObjectName("danger")
        self.deny.clicked.connect(lambda: self.decide(False))
        self.allow.clicked.connect(lambda: self.decide(True))
        buttons.addWidget(self.deny)
        buttons.addWidget(self.allow)
        body.addLayout(buttons)
        self.approval_card.hide()
        page.addWidget(self.approval_card)
        page.addStretch()

    def build_shortcut(self):
        page = self.page("Keyboard shortcut", "One shortcut to start. The same shortcut to stop.")
        group, body = card()
        body.addWidget(label("ACTIVATION", "section"))
        body.addWidget(label("Choose what feels natural"))
        body.addWidget(label("Click the field, then press your preferred combination. For example: Ctrl + Shift + Y.", "muted"))
        self.shortcut_edit = QKeySequenceEdit(QKeySequence(self.settings.shortcut))
        self.shortcut_edit.setMaximumSequenceLength(1)
        self.shortcut_edit.setAccessibleName("Activation shortcut")
        body.addWidget(self.shortcut_edit)
        row = QHBoxLayout()
        self.save_shortcut_button = QPushButton("Save shortcut")
        self.save_shortcut_button.setObjectName("primary")
        self.save_shortcut_button.clicked.connect(self.save_shortcut)
        self.remove_shortcut_button = QPushButton("Disable shortcut")
        self.remove_shortcut_button.clicked.connect(self.remove_shortcut)
        row.addWidget(self.save_shortcut_button)
        row.addWidget(self.remove_shortcut_button)
        row.addStretch()
        body.addLayout(row)
        self.shortcut_message = label("No shortcut is assigned yet. The Start listening button always works.", "muted")
        body.addWidget(self.shortcut_message)
        page.addWidget(group)
        group, body = card()
        body.addWidget(label("HOW IT WORKS", "section"))
        body.addWidget(label("When idle → starts one voice request\nWhile busy → stops recording, speech and remaining steps\nWhile stopping → waits safely; never starts a second task"))
        body.addWidget(label("Letters and numbers require Ctrl or Alt. Function keys are supported, except reserved F12. Windows-key shortcuts and common editing shortcuts are protected. Some apps may reserve combinations without reporting a conflict.", "muted"))
        body.addWidget(label("Stopping cannot undo completed actions or forcibly reverse an OS operation already in progress.", "muted"))
        page.addWidget(group)
        page.addStretch()

    def build_voice(self):
        page = self.page("Voice & microphone", "Calm replies. Listening only when you ask.")
        group, body = card()
        body.addWidget(label("VOICE", "section"))
        self.spoken = QCheckBox("Speak responses aloud")
        self.spoken.setChecked(self.settings.spoken_replies)
        self.spoken.toggled.connect(self.save_voice)
        body.addWidget(self.spoken)
        body.addWidget(label("Configured voice: " + (config.TTS_VOICE if config.TTS_BACKEND == "edge" else config.TTS_LOCAL_VOICE), "muted"))
        body.addWidget(label("Your existing soft voice settings are preserved. Only final replies are spoken. Edge neural speech uses an online service; Windows speech is the fallback.", "muted"))
        page.addWidget(group)
        group, body = card()
        body.addWidget(label("MICROPHONE", "section"))
        self.microphone = QComboBox()
        self.microphone.setAccessibleName("Input microphone")
        self.microphone.addItem("Windows default microphone", None)
        try:
            import pyaudio
            audio = pyaudio.PyAudio()
            try:
                for index in range(audio.get_device_count()):
                    info = audio.get_device_info_by_index(index)
                    if info.get("maxInputChannels", 0) > 0:
                        self.microphone.addItem(info["name"] + f" · {index}", index)
            finally:
                audio.terminate()
        except Exception:
            pass
        index = self.microphone.findData(self.settings.microphone)
        if index < 0:
            self.microphone.addItem("Previously selected device unavailable — choose another", self.settings.microphone)
            index = self.microphone.count() - 1
        self.microphone.setCurrentIndex(index)
        self.microphone.currentIndexChanged.connect(self.save_voice)
        body.addWidget(self.microphone)
        self.pause = QComboBox()
        self.pause.setAccessibleName("Pause before sending a voice command")
        for title, seconds in (("Quick · 0.6 second pause", 0.6), ("Balanced · 0.9 second pause", 0.9), ("Relaxed · 1.4 second pause", 1.4)):
            self.pause.addItem(title, seconds)
        self.pause.setCurrentIndex(self.pause.findData(self.settings.pause_seconds))
        self.pause.currentIndexChanged.connect(self.save_pause)
        body.addWidget(self.pause)
        body.addWidget(label("The microphone is closed when idle, thinking, working or speaking. Recording ends after a natural pause, or is discarded when you press Stop. You have 15 seconds to begin speaking, and up to 25 seconds per command. No wake-word listener runs in desktop mode.", "muted"))
        body.addWidget(label("Local speech recognition is used when configured and available. Online recognition may be used if enabled in your existing settings. Audio is not saved by this desktop interface.", "muted"))
        self.voice_message = label("Changes apply to your next request.", "muted")
        body.addWidget(self.voice_message)
        page.addWidget(group)
        page.addStretch()

    def build_about(self):
        page = self.page("About & privacy", "A desktop companion, with clear boundaries.")
        group, body = card()
        body.addWidget(label("ZENO · Press-to-talk", "heroTitle"))
        body.addWidget(label("Uses your existing ZENO brain, tools, memory and connected awareness sources. This desktop mode does not open a remote-control server."))
        body.addWidget(label("Routine tasks follow your existing permission policy. Deletion and power actions still require approval; high-risk actions ask twice. Approval expires after 60 seconds.", "muted"))
        body.addWidget(label("Requests may be sent to your configured AI provider. Existing conversation memory, audit logs and task reports can contain transcripts or task details. Keep your API keys and account tokens private.", "muted"))
        body.addWidget(label("Closing the window keeps ZENO available in the system tray. Use Quit ZENO to release the shortcut and stop the app. No automatic startup has been enabled.", "muted"))
        body.addWidget(label("Desktop preferences: " + str(self.settings_path), "muted"))
        quit_button = QPushButton("Quit ZENO")
        quit_button.clicked.connect(self.request_quit)
        body.addWidget(quit_button, alignment=Qt.AlignmentFlag.AlignLeft)
        page.addWidget(group)
        page.addStretch()

    def refresh_shortcut(self):
        self.shortcut_hint.setText((self.hotkey.binding + "  ·  Start / stop") if self.hotkey.binding else "Choose a keyboard shortcut in Settings, or use the button below.")

    def save_pause(self):
        self.settings.pause_seconds = self.pause.currentData()
        self.persist()

    def persist(self):
        try:
            self.settings.save(self.settings_path)
            return True
        except OSError:
            QMessageBox.warning(self, "Settings not saved", "The change works for this session, but could not be saved. Check access to your ZENO data folder.")
            return False

    def save_shortcut(self):
        text = self.shortcut_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        try:
            self.hotkey.register(text)
        except ValueError as exc:
            self.shortcut_message.setText(str(exc))
            return
        self.settings.shortcut = text
        saved = self.persist()
        self.shortcut_message.setText("Shortcut saved and active. Press it once to start; again to stop." if saved else "Shortcut active for this session only.")
        self.refresh_shortcut()

    def remove_shortcut(self):
        self.hotkey.close()
        self.hotkey = GlobalHotkey(self.application, self.toggle)
        self.settings.shortcut = ""
        self.shortcut_edit.clear()
        self.persist()
        self.shortcut_message.setText("Shortcut disabled. You can still use Start listening.")
        self.refresh_shortcut()

    def save_voice(self):
        self.settings.spoken_replies = self.spoken.isChecked()
        self.settings.microphone = self.microphone.currentData()
        if self.persist():
            self.voice_message.setText("Saved. Changes apply to your next request.")

    def toggle(self):
        if self.closing:
            return
        if not self.controller.busy:
            focused = self.application.focusWidget()
            if focused is self.shortcut_edit or (focused and self.shortcut_edit.isAncestorOf(focused)):
                return
            # Preserve the user's target app focus (typing/screen tasks depend on it).
            if not self.isVisible():
                self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
                self.show()
                self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
            self.navigation.setCurrentRow(0)
            self.detail.hide()
            self.transcript.setText("Speak after ZENO shows Listening.")
            self.reply.setText("")
        self.controller.activate()

    def send_text(self):
        text = self.input.text().strip()
        if text and not self.controller.busy and not self.closing:
            self.input.clear()
            self.detail.hide()
            self.transcript.setText("You: " + text)
            self.reply.setText("")
            self.controller.activate(text)

    def on_event(self, kind, value):
        if kind == "state":
            # Ignore a worker state queued just before the user pressed stop.
            if self.controller.control and self.controller.control.cancelled.is_set() and value not in {"Ready", "Stopping"}:
                return
            self.overlay.handle_event(kind, value)
            self.status.setText(value)
            busy = value != "Ready"
            self.mark.active = busy
            self.mark.update()
            self.hero_title.setText({"Ready": "Ready when you are", "Listening": "I'm listening", "Stopping": "Stopping safely…"}.get(value, value + "…"))
            self.start_button.setText("Stop" if busy else "Start listening")
            self.start_button.setEnabled(value != "Stopping")
            for widget in (self.send, self.input, self.save_shortcut_button, self.remove_shortcut_button, self.shortcut_edit):
                widget.setEnabled(not busy)
            self.side_status.setText("●  Microphone on" if value == "Listening" else "●  Microphone off")
            self.tray.setToolTip("ZENO — " + value.lower())
            if value == "Stopping":
                self.approval_card.hide()
        elif kind == "transcript":
            self.overlay.handle_event(kind, value)
            self.transcript.setText("You: " + value)
            self.reply.setText("")
        elif kind == "reply":
            self.overlay.handle_event(kind, value)
            self.reply.setText(value)
            if self.detail.text() == value:
                self.detail.hide()
        elif kind == "detail":
            self.detail.setText(value)
            self.detail.show()
        elif kind == "draft":
            self.input.setText(value)
        elif kind == "level":
            self.overlay.handle_event(kind, value)

    def on_approval(self, request_id, prompt):
        self.approval_id = request_id
        if not request_id or (self.controller.control and self.controller.control.cancelled.is_set()):
            self.approval_card.hide()
            return
        self.reveal()
        self.navigation.setCurrentRow(0)
        self.approval_prompt.setText(prompt)
        self.allow.setEnabled(True)
        self.deny.setEnabled(True)
        self.approval_card.show()
        self.deny.setFocus()
        scroll = self.pages.currentWidget()
        QTimer.singleShot(0, lambda: scroll.ensureWidgetVisible(self.approval_card))

    def decide(self, approved):
        self.controller.answer_approval(self.approval_id, approved)
        self.allow.setEnabled(False)
        self.deny.setEnabled(False)

    def reveal(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def on_idle(self):
        self.approval_card.hide()
        if self.closing:
            self.finish_quit()

    def request_quit(self):
        self.closing = True
        self.hotkey.close()
        if self.controller.busy:
            self.controller.stop()
        else:
            self.finish_quit()

    def finish_quit(self):
        self.overlay.close()
        if self.controller.engine:
            self.controller.engine.close()
        self.tray.hide()
        self.application.quit()

    def closeEvent(self, event):
        if self.tray.isVisible() and not self.closing:
            self.hide()
            event.ignore()
        else:
            event.ignore()
            self.request_quit()


def run_desktop():
    if sys.platform != "win32":
        print("ZENO desktop currently supports Windows only.")
        return 1
    application = QApplication(sys.argv[:1])
    application.setApplicationName("ZENO")
    application.setQuitOnLastWindowClosed(False)
    application.setStyle("Fusion")
    application.setStyleSheet(STYLE)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(config.DATA_DIR / "desktop.lock"))
    if not lock.tryLock(0):
        QMessageBox.information(None, "ZENO is already running", "Open ZENO from its system-tray icon. Only one desktop instance can own the shortcut.")
        return 1
    settings_path = config.DATA_DIR / "desktop.json"
    window = DesktopWindow(application, DesktopSettings.load(settings_path), settings_path)
    window.show()
    try:
        return application.exec()
    finally:
        window.hotkey.close()
        lock.unlock()
