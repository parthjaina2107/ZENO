"""Desktop coordinator: one black dashboard and one compact island."""
import sys

from PySide6.QtCore import QObject, Qt, QLockFile
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from config import config
from .controller import DesktopController
from .hotkey import GlobalHotkey
from .settings import DesktopSettings
from .overlay import ActivityOverlay


def app_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor('#202020'))
    painter.drawRoundedRect(2, 2, 60, 60, 18, 18)
    painter.setPen(QColor('white'))
    font = painter.font()
    font.setPixelSize(34)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, 'Z')
    painter.end()
    return QIcon(pixmap)


class DesktopApplication(QObject):
    def __init__(self, application, settings, settings_path, controller=None):
        super().__init__()
        self.application, self.settings, self.settings_path = application, settings, settings_path
        self.controller = controller or DesktopController(settings)
        self.overlay = ActivityOverlay()
        self.dashboard = None
        self.closing = False
        self.capturing_shortcut = False
        self.approval_id = ''
        self.hotkey = GlobalHotkey(application, self.toggle)
        self.overlay.dashboard_requested.connect(self.open_dashboard)
        self.overlay.settings_requested.connect(self.reveal)
        self.overlay.start_requested.connect(self.toggle)
        self.overlay.conversation_requested.connect(self.listen_conversation)
        self.overlay.stop_requested.connect(self.controller.stop)
        self.overlay.text_requested.connect(self.send_island_text)
        self.overlay.approval_decided.connect(self.decide_island)
        self.controller.event.connect(self.on_event)
        self.controller.approval.connect(self.on_approval)
        self.controller.idle.connect(self.on_idle)
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip('ZENO - microphone off')
        menu = QMenu()
        menu.addAction('Open dashboard', self.open_dashboard)
        menu.addAction('Preferences', self.reveal)
        menu.addAction('Show island', self.overlay.show)
        menu.addAction('Start / stop', self.toggle)
        menu.addSeparator()
        menu.addAction('Quit ZENO', self.request_quit)
        self.tray_menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.open_dashboard() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        self.settings_message = ''
        if settings.shortcut:
            try:
                self.hotkey.register(settings.shortcut)
            except ValueError as exc:
                self.settings_message = str(exc)

    def toggle(self):
        if not self.closing and not (self.capturing_shortcut and not self.controller.busy):
            self.controller.activate(chat_only=self.overlay.chat_only)

    def send_island_text(self, text):
        if text.strip() and not self.controller.busy and not self.closing:
            self.controller.activate(text)

    def listen_conversation(self):
        if not self.closing and not self.controller.busy:
            self.controller.activate(chat_only=True)

    def decide_island(self, request_id, approved):
        if request_id == self.approval_id:
            self.controller.answer_approval(request_id, approved)
            self.overlay.allow.setEnabled(False)
            self.overlay.deny.setEnabled(False)

    def on_event(self, kind, value):
        if kind == 'state' and self.controller.control and self.controller.control.cancelled.is_set() and value not in {'Ready', 'Stopping'}:
            return
        self.overlay.handle_event(kind, value)
        if self.dashboard:
            self.dashboard.handle_event(kind, value)
        if kind == 'state':
            self.tray.setToolTip('ZENO - ' + value.lower())

    def on_approval(self, request_id, prompt):
        if self.controller.control and self.controller.control.cancelled.is_set():
            request_id = ''
        self.approval_id = request_id
        self.overlay.set_approval(request_id, prompt)
        if self.dashboard:
            self.dashboard.set_approval(request_id, prompt)

    def open_dashboard(self):
        if self.closing:
            return
        if self.dashboard is None:
            from .dashboard import DashboardWindow
            self.dashboard = DashboardWindow(self.overlay)
            self.dashboard.bridge.conversation_requested.connect(self.listen_conversation)
            self.dashboard.bridge.settings_request.connect(self.handle_settings)
            self.dashboard.bridge.quit_requested.connect(self.request_quit)
            self.dashboard.bridge.capture_changed.connect(self.set_capture)
            self.dashboard.setWindowIcon(app_icon())
        self.dashboard.show()
        self.dashboard.raise_()
        self.dashboard.activateWindow()

    def reveal(self):
        self.open_dashboard()
        if self.dashboard:
            self.dashboard.show_preferences()

    def set_capture(self, capturing):
        self.capturing_shortcut = capturing

    def microphones(self):
        devices = [{'id': None, 'name': 'Windows default microphone'}]
        try:
            import pyaudio
            audio = pyaudio.PyAudio()
            try:
                for index in range(audio.get_device_count()):
                    info = audio.get_device_info_by_index(index)
                    if info.get('maxInputChannels', 0) > 0:
                        devices.append({'id': index, 'name': info['name'] + ' - ' + str(index)})
            finally:
                audio.terminate()
        except Exception:
            pass
        if self.settings.microphone not in [item['id'] for item in devices]:
            devices.append({'id': self.settings.microphone, 'name': 'Previously selected device (unavailable)'})
        return devices

    def handle_settings(self, raw):
        import json
        data = json.loads(raw)
        message = self.settings_message
        if data.get('type') == 'save_desktop_settings':
            if self.controller.busy:
                self.publish_settings('Stop or finish the current task before changing settings.')
                return
            shortcut = data.get('shortcut')
            spoken = data.get('spoken_replies')
            microphone = data.get('microphone')
            pause = data.get('pause_seconds')
            if (not isinstance(shortcut, str) or len(shortcut) > 64 or type(spoken) is not bool
                    or (microphone is not None and type(microphone) is not int)
                    or pause not in (0.6, 0.9, 1.4)):
                self.publish_settings('Invalid settings. Please review your choices.')
                return
            if microphone not in [item['id'] for item in self.microphones()]:
                self.publish_settings('That microphone is unavailable. Choose another input.')
                return
            try:
                if shortcut:
                    self.hotkey.register(shortcut)
                else:
                    self.hotkey.close()
                    self.hotkey = GlobalHotkey(self.application, self.toggle)
            except ValueError as exc:
                self.publish_settings(str(exc))
                return
            self.settings.shortcut = shortcut
            self.settings.spoken_replies = spoken
            self.settings.microphone = microphone
            self.settings.pause_seconds = pause
            try:
                self.settings.save(self.settings_path)
                message = 'Saved. Changes apply to your next request.'
            except OSError:
                message = 'Applied for this session, but could not save to your data folder.'
            self.settings_message = message
        self.publish_settings(message)

    def publish_settings(self, message=''):
        if self.dashboard:
            self.dashboard.bridge.publish({
                'type': 'desktop_settings', 'shortcut': self.settings.shortcut,
                'spoken_replies': self.settings.spoken_replies,
                'microphone': self.settings.microphone, 'pause_seconds': self.settings.pause_seconds,
                'microphones': self.microphones(), 'message': message,
            })

    def on_idle(self):
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
        if self.dashboard:
            self.dashboard.hide()
        self.overlay.close()
        if self.controller.engine:
            self.controller.engine.close()
        self.tray.hide()
        self.application.quit()


def run_desktop():
    if sys.platform != 'win32':
        print('ZENO desktop currently supports Windows only.')
        return 1
    application = QApplication(sys.argv[:1])
    application.setApplicationName('ZENO')
    application.setQuitOnLastWindowClosed(False)
    application.setStyle('Fusion')
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(config.DATA_DIR / 'desktop.lock'))
    if not lock.tryLock(0):
        QMessageBox.information(None, 'ZENO is already running', 'Open ZENO from its system-tray icon. Only one desktop instance can own the shortcut.')
        return 1
    settings_path = config.DATA_DIR / 'desktop.json'
    desktop = DesktopApplication(application, DesktopSettings.load(settings_path), settings_path)
    desktop.overlay.show()
    try:
        return application.exec()
    finally:
        desktop.hotkey.close()
        lock.unlock()
