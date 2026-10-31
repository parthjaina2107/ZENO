"""Persistent desktop island; forwards intent to the existing desktop controller."""
import math

from PySide6.QtCore import Qt, QTimer, QRectF, Signal, QVariantAnimation, QEasingCurve, QPointF
from PySide6.QtGui import QColor, QCursor, QPainter, QLinearGradient, QRadialGradient, QPen, QPainterPath, QConicalGradient
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget, QHBoxLayout, QPushButton, QLineEdit, QScrollArea, QGraphicsOpacityEffect, QSizePolicy
from .light_engine import MicrophoneLights
from .island_components import ActivityBars, BrandMark, GlassButton


class ActivityOverlay(QWidget):
    start_requested = Signal()
    conversation_requested = Signal()
    stop_requested = Signal()
    text_requested = Signal(str)
    settings_requested = Signal()
    dashboard_requested = Signal()
    approval_decided = Signal(str, bool)

    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAccessibleName("ZENO desktop island")
        self.setWindowTitle("ZENO — Desktop island")
        self.busy = False
        self.request_id = ""
        self.typing = False
        self.expanded = False
        self._drag_offset = None
        self._reveal = 0.0
        self.expanded_size = (480, 400)
        self._glow = 0.0
        self._pointer = QPointF(150, 34)
        self._phase = 0.0
        self._pointer_inside = False
        self.reduced_motion = False
        self.service_error = False
        self.last_request = ''
        self.microphone_active = False
        self.chat_only = False
        self.lights = MicrophoneLights()
        self.setMouseTracking(True)
        self.motion = QVariantAnimation(self)
        self.motion.setDuration(380)
        self.motion.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.motion.valueChanged.connect(self._animate_reveal)
        self.motion.finished.connect(self._finish_reveal)
        self.ambient = QTimer(self)
        self.ambient.setInterval(33)
        self.ambient.timeout.connect(self._track_pointer)
        self.setStyleSheet("""
            * { font-family: 'Segoe UI'; }
            QLabel { color: #e4eaf5; background: transparent; border: none; font-size: 12px; }
            QLineEdit { color: #e8efff; background: rgba(16,24,40,230); border: 1px solid rgba(129,157,209,65);
                        border-radius: 12px; padding: 11px 14px; font-size: 12px; }
            QLineEdit:focus { border-color: #9aaee7; }
            QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 4px; }
            QScrollBar::handle:vertical { background: #3f516e; border-radius: 2px; min-height: 24px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        self.header = QWidget(self)
        header = QHBoxLayout(self.header)
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        self.mark = BrandMark()
        self.title = QLabel("zeno")
        self.title.setStyleSheet("font-weight: 700; font-size: 15px; letter-spacing: -0.5px;")
        self.status = QLabel("Ready")
        self.status.setStyleSheet("color: #7f90ac; font-size: 10px;")
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.start = GlassButton('Talk', 'mic', primary=True)
        self.start.setFixedWidth(78)
        self.start.setAccessibleName('Start listening, retry, or stop current task')
        self.start.clicked.connect(self.activate)
        header.addWidget(self.mark)
        header.addWidget(self.title)
        header.addWidget(self.status, 1)
        header.addWidget(self.start)
        self.body = QWidget(self)
        self.body_opacity = QGraphicsOpacityEffect(self.body)
        self.body.setGraphicsEffect(self.body_opacity)
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)
        self.bars = ActivityBars(self)
        body.addWidget(self.bars)
        self.eyebrow = QLabel('YOUR NEXT MOVE')
        self.eyebrow.setStyleSheet('color: #687b9c; font-size: 9px; letter-spacing: 1.8px; padding-top: 2px;')
        body.addWidget(self.eyebrow)
        self.caption = QLabel('What would you like to do?\nSpeak a thought, or make it a quick command.')
        self.caption.setStyleSheet('font-size: 14px; color: #c3cde0; padding: 0px 1px;')
        self.caption.setTextFormat(Qt.TextFormat.PlainText)
        self.caption.setWordWrap(True)
        self.caption.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.caption.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.caption)
        scroll.setMinimumHeight(62)
        body.addWidget(scroll, 1)
        self.entry = QLineEdit()
        self.entry.setPlaceholderText('Give ZENO a direction…')
        self.entry.setAccessibleName('Island command')
        self.entry.returnPressed.connect(self.submit)
        self.entry.hide()
        body.addWidget(self.entry)
        self.approval_row = QWidget()
        approval_layout = QHBoxLayout(self.approval_row)
        approval_layout.setContentsMargins(0, 0, 0, 0)
        approval_layout.setSpacing(10)
        self.deny = GlassButton('Deny')
        self.allow = GlassButton('Approve action', 'shield-check', primary=True)
        self.deny.clicked.connect(lambda: self.decide(False))
        self.allow.clicked.connect(lambda: self.decide(True))
        approval_layout.addWidget(self.deny)
        approval_layout.addWidget(self.allow)
        body.addWidget(self.approval_row)
        self.approval_row.hide()
        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.type_button = GlassButton('Type a request', 'keyboard', 'A shortcut to getting it done')
        self.type_button.clicked.connect(self.enable_typing)
        self.dashboard_button = GlassButton('Open workspace', 'layout-dashboard', 'Your full dashboard')
        self.dashboard_button.clicked.connect(self.dashboard_requested.emit)
        actions.addWidget(self.type_button, 1)
        actions.addWidget(self.dashboard_button, 1)
        body.addLayout(actions)
        footer = QHBoxLayout()
        footer.setSpacing(10)
        self.settings_button = GlassButton('Preferences', 'sliders-horizontal', quiet=True)
        self.settings_button.clicked.connect(self.settings_requested.emit)
        self.mode_button = GlassButton('Assistant', quiet=True)
        self.mode_button.setCheckable(True)
        self.mode_button.setAccessibleName('Conversation only mode')
        self.mode_button.clicked.connect(self.toggle_conversation)
        self.collapse_button = GlassButton('Minimize', 'chevron-up', quiet=True)
        self.collapse_button.clicked.connect(self.collapse)
        self.privacy = QLabel('Mic off')
        self.privacy.setStyleSheet('color: #64738e; font-size: 10px;')
        footer.addWidget(self.settings_button)
        footer.addWidget(self.mode_button)
        footer.addStretch()
        footer.addWidget(self.privacy)
        footer.addWidget(self.collapse_button)
        body.addLayout(footer)
        self.dismiss = QTimer(self)
        self.dismiss.setSingleShot(True)
        self.dismiss.timeout.connect(self._auto_collapse)
        self.body.hide()
        self.setFixedSize(300, 68)
        self._layout_contents()
        self.position_at_top()
        app = QApplication.instance()
        app.screenAdded.connect(lambda screen: self.position_at_top())
        app.screenRemoved.connect(lambda screen: self.position_at_top())
        for screen in app.screens():
            screen.availableGeometryChanged.connect(lambda area: self.position_at_top())

    def position_at_top(self):
        screen = QApplication.screenAt(self.pos()) or QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.move(area.center().x() - self.width() // 2, area.top() + 16)

    def expand(self):
        self.dismiss.stop()
        self.body.layout().activate()
        target_height = max(400, 94 + self.body.minimumSizeHint().height())
        resized_content = self.expanded_size[1] != target_height
        self.expanded_size = (480, target_height)
        if not self.expanded or resized_content:
            self.expanded = True
            self.body.show()
            self._transition(1.0)
        self.show()

    def collapse(self):
        if self.request_id:
            return  # Keep a pending approval visible until answered or expired.
        self.dismiss.stop()
        self.expanded = False
        self.entry.hide()
        if self.typing:
            self.typing = False
            self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
        self._transition(0.0)
        self.show()

    def _transition(self, target):
        # Reverse from the current frame instead of snapping on rapid hover changes.
        self.motion.stop()
        self._anchor_x = self.x() + self.width() / 2
        screen = self.screen() or QApplication.primaryScreen()
        self._expanded_width = min(self.expanded_size[0], screen.availableGeometry().width() - 24)
        self._expanded_height = min(self.expanded_size[1], screen.availableGeometry().height() - 48)
        self._animation_start = (self.width(), self.height(), self._reveal)
        self._animation_target = target
        self.motion.setStartValue(0.0)
        self.motion.setEndValue(1.0)
        self.motion.setDuration(max(120, int(380 * abs(target - self._reveal))))
        self.motion.start()
        if self.reduced_motion:
            self.motion.setCurrentTime(self.motion.duration())

    def _animate_reveal(self, value):
        start_width, start_height, start_reveal = self._animation_start
        self._reveal = start_reveal + (self._animation_target - start_reveal) * float(value)
        end_width = self._expanded_width if self._animation_target else self._compact_width()
        end_height = self._expanded_height if self._animation_target else 68
        width = round(start_width + (end_width - start_width) * float(value))
        height = round(start_height + (end_height - start_height) * float(value))
        self.setFixedSize(width, height)
        self.move(round(self._anchor_x - width / 2), self.y())
        self._layout_contents()
        self.body_opacity.setOpacity(max(0.0, (self._reveal - 0.25) / 0.75))
        self.update()

    def _layout_contents(self):
        self.header.setVisible(not self.microphone_active or self.expanded)
        self.header.setGeometry(24, 16, self.width() - 48, 36)
        # Fixed-height content is clipped by the growing window, never squashed.
        self.body.setGeometry(24, 72, self.width() - 48, getattr(self, '_expanded_height', 400) - 94)

    def _compact_width(self):
        screen = self.screen() or QApplication.primaryScreen()
        return min(600, screen.availableGeometry().width() - 24) if self.microphone_active else 300

    def _finish_reveal(self):
        if not self.expanded:
            self.body.hide()

    def _track_pointer(self):
        local = self.mapFromGlobal(QCursor.pos())
        inside = self.rect().contains(local)
        # Child controls and focus changes can swallow QWidget leave events.
        # Use the actual pointer position for hover state across the whole island.
        if inside != self._pointer_inside:
            self._pointer_inside = inside
            if inside and not self.microphone_active:
                self.expand()
            else:
                self._schedule_collapse()
        if not inside and self.expanded and not self.request_id and not self.dismiss.isActive() and self._drag_offset is None:
            self._schedule_collapse()
        self._glow += ((1.0 if inside and not self.reduced_motion else 0.0) - self._glow) * 0.16
        if inside:
            self._pointer += (QPointF(local) - self._pointer) * 0.18
        if not self.reduced_motion:
            self._phase += 0.018
        self.bars.pointer = self.bars.mapFrom(self, self._pointer.toPoint())
        self.bars.presence = self._glow if not self.reduced_motion else 0
        self.bars.reduced_motion = self.reduced_motion
        if self.expanded and not self.reduced_motion:
            self.bars.phase += .018
        for button in (self.start, self.type_button, self.dashboard_button, self.settings_button, self.mode_button, self.collapse_button, self.allow, self.deny):
            button.reduced_motion = self.reduced_motion
        if self.expanded:
            self.bars.update()
        if self.expanded or self.microphone_active or self._glow > 0.01:
            self.update()

    def _schedule_collapse(self):
        if self.expanded and not self.request_id and self._drag_offset is None and (not self.dismiss.isActive() or self.dismiss.remainingTime() > 550):
            self.dismiss.start(550)

    def _auto_collapse(self):
        if not self.rect().contains(self.mapFromGlobal(QCursor.pos())) and self._drag_offset is None:
            self.collapse()

    def activate(self):
        if self.busy:
            self.stop_requested.emit()
        elif self.service_error and self.last_request:
            from brain.companion import conversation_text
            text = self.last_request
            if self.chat_only and conversation_text(text) is None:
                text = 'Chat: ' + text
            self.text_requested.emit(text)
        elif self.chat_only:
            self.conversation_requested.emit()
        else:
            self.start_requested.emit()

    def toggle_conversation(self):
        if self.busy or self.request_id:
            self.mode_button.setChecked(self.chat_only)
            return
        self.chat_only = not self.chat_only
        self.mode_button.setChecked(self.chat_only)
        self.mode_button.setText('Just talk' if self.chat_only else 'Assistant')
        self.eyebrow.setText('JUST TALK' if self.chat_only else 'YOUR NEXT MOVE')
        self.entry.setPlaceholderText("What's on your mind?" if self.chat_only else 'Give ZENO a direction…')
        self.caption.setText('Conversation only. No computer actions. What is on your mind?'
                             if self.chat_only else 'Ready for a request. Ask what I can do, or give me a task.')

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self.busy or self.request_id:
                self.stop_requested.emit()
            else:
                self.collapse()
            event.accept()
            return
        super().keyPressEvent(event)

    def enable_typing(self):
        if self.busy:
            return
        self.typing = True
        self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, False)
        self.entry.show()
        self.expand()
        self.activateWindow()
        self.entry.setFocus()

    def submit(self):
        text = self.entry.text().strip()
        if text and not self.busy:
            self.entry.clear()
            self.entry.hide()
            self.typing = False
            self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
            self.show()
            self.text_requested.emit('Chat: ' + text if self.chat_only else text)

    def set_approval(self, request_id, prompt):
        self.request_id = request_id
        self.approval_row.setVisible(bool(request_id))
        if request_id:
            self.allow.setEnabled(True)
            self.deny.setEnabled(True)
            self.caption.setText(prompt)
            self.expand()

    def decide(self, approved):
        if self.request_id:
            self.allow.setEnabled(False)
            self.deny.setEnabled(False)
            self.approval_decided.emit(self.request_id, approved)

    def paintEvent(self, event):
        if self.microphone_active and not self.expanded:
            self._paint_listening_island()
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        surface = QRectF(self.rect()).adjusted(5, 4, -5, -5)
        shape = QPainterPath()
        shape.addRoundedRect(surface, 30, 30)
        painter.setClipPath(shape)
        painter.setPen(Qt.PenStyle.NoPen)
        glass = QLinearGradient(0, 0, self.width(), self.height())
        glass.setColorAt(0, QColor(16, 21, 33, 253))
        glass.setColorAt(0.5, QColor(8, 12, 22, 253))
        glass.setColorAt(1, QColor(6, 9, 17, 253))
        painter.setBrush(glass)
        painter.drawRoundedRect(surface, 30, 30)
        if self.microphone_active:
            spectrum = QConicalGradient(surface.center(), 0 if self.reduced_motion else self._phase * 45)
            for stop, color in [(0, '#71dccb'), (.3, '#91cfff'), (.6, '#ae8efa'), (.85, '#efb18e'), (1, '#71dccb')]:
                spectrum.setColorAt(stop, QColor(color))
            painter.setPen(QPen(spectrum, 2))
            painter.drawRoundedRect(surface.adjusted(1, 1, -1, -1), 30, 30)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#71dccb'))
            painter.drawEllipse(QPointF(self.width() - 18, 19), 3, 3)
        # Soft silver pools echo the dashboard's ambient background and cursor halo.
        for point, radius, alpha in [
            (QPointF(self.width() * (0.8 + 0.1 * math.sin(self._phase)), 15), 240, 22),
            (QPointF(30, self.height()), 180, 14),
            (self._pointer, 115, round(72 * self._glow)),
        ]:
            glow = QRadialGradient(point, radius)
            glow.setColorAt(0, QColor(255, 255, 255, alpha))
            glow.setColorAt(1, QColor(255, 255, 255, 0))
            painter.fillRect(surface, glow)
        if self._reveal > 0:
            panel = QRectF(16, 65, self.width() - 32, self.height() - 82)
            painter.setPen(QPen(QColor(246, 246, 246, 20), 1))
            painter.setBrush(QColor(255, 255, 255, 5))
            painter.drawRoundedRect(panel, 20, 20)
        painter.setClipping(False)
        rim = QLinearGradient(0, 0, self.width(), self.height())
        rim.setColorAt(0, QColor(255, 255, 255, 78))
        rim.setColorAt(0.5, QColor(255, 255, 255, 18))
        rim.setColorAt(1, QColor(255, 255, 255, 40))
        painter.setPen(QPen(rim, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(surface, 30, 30)

    def _paint_listening_island(self):
        """Contained cyan activity, with actual capture levels driving the bars."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        surface = QRectF(self.rect()).adjusted(5, 4, -5, -5)
        shape = QPainterPath()
        shape.addRoundedRect(surface, 22, 22)
        p.setClipPath(shape)
        p.fillPath(shape, QColor('#080e12'))
        phase = 0 if self.reduced_motion else self._phase
        glow = QRadialGradient(QPointF(self.width() - 18, 38), 108)
        glow.setColorAt(0, QColor(24, 216, 223, round(125 + 25 * math.sin(phase * 2))))
        glow.setColorAt(.45, QColor(15, 171, 185, 65))
        glow.setColorAt(1, QColor(8, 14, 18, 0))
        p.fillPath(shape, glow)
        font = p.font()
        font.setFamily('Segoe UI')
        font.setPixelSize(16)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor('#f1f6f7'))
        p.drawText(QRectF(30, 4, self.width() - 130, 59), Qt.AlignmentFlag.AlignVCenter, 'Listening')
        p.setPen(Qt.PenStyle.NoPen)
        for index in range(5):
            motion = .5 + .5 * math.sin(phase * 8 + index * 1.15)
            height = 5 if self.reduced_motion else 5 + 5 * motion + self.bars.level * (8 + 13 * motion)
            p.setBrush(QColor('#9af5f1'))
            p.drawRoundedRect(QRectF(self.width() - 88 + index * 8, 34 - height / 2, 4, height), 2, 2)

    def handle_event(self, kind, value):
        if kind == "state":
            if value in {'Ready', 'Stopping'}:
                self.handle_event('microphone', 'off')
            self.dismiss.stop()
            self.busy = value != "Ready"
            self.bars.state = 'AI unavailable' if value == 'Ready' and self.service_error else value
            self.bars.level = 0
            if value == 'Preparing':
                self.service_error = False
            self.status.setText('AI unavailable' if value == 'Ready' and self.service_error else value)
            self.start.setText("Stop" if self.busy else "Retry" if self.service_error and self.last_request else "Talk")
            self.start.glyph = "square" if self.busy else "mic"
            self.start.setEnabled(value != "Stopping")
            self.type_button.setEnabled(not self.busy)
            self.mode_button.setEnabled(not self.busy)
            if value == "Preparing":
                self.caption.setText("Getting ready. Use Stop or your shortcut to cancel.")
                self.expand()
            if value == "Ready":
                self.bars.timer.stop()
                self.set_approval("", "")
                if self.expanded:
                    self.dismiss.start(6000)
            else:
                self.bars.timer.start()
            if value == "Stopping":
                self.set_approval("", "")
            self.show()
            self.bars.update()
        elif kind == 'microphone':
            self.microphone_active = value == 'on'
            self.bars.capture_active = self.microphone_active
            if not self.microphone_active:
                self.bars.level = 0
            self.bars.update()
            self.eyebrow.setText('LIVE CAPTURE' if self.microphone_active else 'JUST TALK' if self.chat_only else 'YOUR NEXT MOVE')
            self.privacy.setText('Mic on' if self.microphone_active else 'Mic off')
            self.lights.set_active(False)
            if self.microphone_active:
                self.position_at_top()
                self.collapse()
                self.raise_()
            elif not self.expanded:
                self._transition(0.0)
            self._layout_contents()
            self.update()
        elif kind == 'service_error':
            self.service_error = True
            self.bars.state = 'AI unavailable'
            self.bars.update()
            self.status.setText('AI unavailable')
        elif kind == "level" and self.bars.state == "Listening":
            self.bars.level = max(0.0, min(1.0, float(value)))
            self.lights.level = self.bars.level
        elif kind in {"transcript", "reply", "detail"}:
            if kind == 'transcript':
                self.last_request = value
            if not self.request_id:
                self.caption.setText(value)
        elif kind == "draft":
            self.entry.setText(value)
            self.caption.setText("Recognition was uncertain. Choose Type a request to review and send this draft.")

    def enterEvent(self, event):
        if not self.microphone_active:
            self.expand()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._schedule_collapse()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self.microphone_active and not self.expanded and event.button() == Qt.MouseButton.LeftButton:
            self.expand()
            return
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 54:
            self.motion.stop()
            self._drag_offset = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None:
            position = event.globalPosition().toPoint() - self._drag_offset
            screen = QApplication.screenAt(event.globalPosition().toPoint()) or QApplication.primaryScreen()
            area = screen.availableGeometry()
            self.move(max(area.left(), min(position.x(), area.right() - self.width() + 1)),
                      max(area.top(), min(position.y(), area.bottom() - self.height() + 1)))

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        self._transition(1.0 if self.expanded else 0.0)

    def showEvent(self, event):
        self.ambient.start()
        if self.busy:
            self.bars.timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.lights.set_active(False)
        self.bars.timer.stop()
        self.ambient.stop()
        super().hideEvent(event)
