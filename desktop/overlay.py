"""Persistent desktop island; forwards intent to the existing desktop controller."""
import math

from PySide6.QtCore import Qt, QTimer, QRectF, Signal, QVariantAnimation, QEasingCurve, QPointF
from PySide6.QtGui import QColor, QCursor, QPainter, QLinearGradient, QRadialGradient, QPen, QPainterPath, QConicalGradient
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget, QHBoxLayout, QPushButton, QLineEdit, QScrollArea, QGraphicsOpacityEffect, QSizePolicy
from .light_engine import MicrophoneLights
from .island_components import ActivityBars, BrandMark, GlassButton, paint_metal_shell


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
        self._spotlight_hue = 220.0
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
        self.motion.setEasingCurve(QEasingCurve.Type.OutQuint)
        self.motion.valueChanged.connect(self._animate_reveal)
        self.motion.finished.connect(self._finish_reveal)
        self.ambient = QTimer(self)
        self.ambient.setInterval(33)
        self.ambient.timeout.connect(self._track_pointer)
        self.setStyleSheet("""
            * { font-family: 'Segoe UI'; }
            QLabel { color: #f2f2f4; background: transparent; border: none; font-size: 12px; }
            QLineEdit { color: #f5f5f7; background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #282a35,stop:1 #15161e); border: 1px solid #616574;
                        border-radius: 16px; padding: 12px 14px; font-size: 12px; }
            QLineEdit:focus { border-color: #a5c9ff; }
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
        self.title.setStyleSheet("font-weight: 600; font-size: 16px; letter-spacing: -0.6px;")
        self.status = QLabel("Ready")
        self.status.setStyleSheet("color: #a1a1aa; font-size: 11px;")
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
        self.body_scroll = QScrollArea(self)
        self.body_scroll.setWidgetResizable(True)
        self.body_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body_scroll.setWidget(self.body)
        self.body_scroll.hide()
        self.body_opacity = QGraphicsOpacityEffect(self.body)
        self.body.setGraphicsEffect(self.body_opacity)
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)
        self.bars = ActivityBars(self)
        body.addWidget(self.bars)
        self.eyebrow = QLabel('AT YOUR COMMAND')
        self.eyebrow.setStyleSheet('color: #a1a1aa; font-size: 9px; letter-spacing: 1.8px; padding-top: 4px;')
        body.addWidget(self.eyebrow)
        self.caption = QLabel('A little space.\nFor your next big idea.')
        self.caption.setStyleSheet('font-size: 19px; font-weight: 500; color: #efeff2; padding: 0px 1px;')
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
        self.type_button = GlassButton('Type a request', 'keyboard', 'Put a thought in motion')
        self.type_button.clicked.connect(self.enable_typing)
        self.dashboard_button = GlassButton('Open workspace', 'layout-dashboard', 'The bigger picture')
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
        self.privacy.setStyleSheet('color: #a1a1aa; font-size: 10px;')
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
        self.body.setMinimumHeight(self.body.minimumSizeHint().height())
        target_height = max(400, 94 + self.body.minimumHeight())
        resized_content = self.expanded_size[1] != target_height
        self.expanded_size = (480, target_height)
        if not self.expanded or resized_content:
            self.expanded = True
            self.body_scroll.show()
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
        screen = self.screen() or QApplication.primaryScreen()
        area = screen.availableGeometry()
        x = max(area.left(), min(round(self._anchor_x - width / 2), area.right() + 1 - width))
        y = max(area.top(), min(self.y(), area.bottom() + 1 - height))
        self.move(x, y)
        self._layout_contents()
        self.body_opacity.setOpacity(max(0.0, (self._reveal - 0.25) / 0.75))
        self.update()

    def _layout_contents(self):
        self.header.setVisible(not self.microphone_active or self.expanded)
        self.header.setGeometry(24, 16, self.width() - 48, 36)
        # Fixed-height content is clipped by the growing window, never squashed.
        self.body_scroll.setGeometry(24, 72, self.width() - 48, getattr(self, '_expanded_height', 400) - 94)

    def _compact_width(self):
        screen = self.screen() or QApplication.primaryScreen()
        return min(360 if self.microphone_active else 300, screen.availableGeometry().width() - 24)

    def _finish_reveal(self):
        if not self.expanded:
            self.body.hide()
            self.body_scroll.hide()

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
            screen = self.screen() or QApplication.primaryScreen()
            area = screen.availableGeometry()
            xp = max(0.0, min(1.0, (QCursor.pos().x() - area.left()) / max(1, area.width())))
            self._spotlight_hue = (220 + xp * 200) % 360
        if not self.reduced_motion:
            self._phase += 0.018
        self.bars.pointer = self.bars.mapFrom(self, self._pointer.toPoint())
        self.bars.presence = self._glow if not self.reduced_motion else 0
        self.bars.spotlight_hue = self._spotlight_hue
        self.bars.reduced_motion = self.reduced_motion
        if self.expanded and not self.reduced_motion:
            self.bars.phase += .018
        for button in (self.start, self.type_button, self.dashboard_button, self.settings_button, self.mode_button, self.collapse_button, self.allow, self.deny):
            button.reduced_motion = self.reduced_motion
            button.pointer = QPointF(button.mapFrom(self, self._pointer.toPoint()))
            button.presence = self._glow if not self.reduced_motion else 0
            button.spotlight_hue = self._spotlight_hue
            if self.expanded or self._glow > .01:
                button.update()
        if self.expanded:
            self.bars.update()
        if not self.reduced_motion or self.expanded or self.microphone_active or self._glow > 0.01:
            self.update()

    def _schedule_collapse(self):
        if self.expanded and not self.typing and not self.request_id and self._drag_offset is None and (not self.dismiss.isActive() or self.dismiss.remainingTime() > 550):
            self.dismiss.start(550)

    def _auto_collapse(self):
        if not self.typing and not self.rect().contains(self.mapFromGlobal(QCursor.pos())) and self._drag_offset is None:
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
        self.eyebrow.setText('JUST TALK' if self.chat_only else 'AT YOUR COMMAND')
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
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        surface = QRectF(self.rect()).adjusted(5, 4, -5, -5)
        radius = 29 + 7 * self._reveal
        # A tight, layered shadow stays inside the transparent native window.
        for spread, alpha in [(4, 12), (2, 24)]:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, alpha))
            p.drawRoundedRect(surface.adjusted(-spread, 0, spread, spread), radius, radius)
        shape = QPainterPath()
        shape.addRoundedRect(surface, radius, radius)
        p.setClipPath(shape)
        paint_metal_shell(p, surface, radius, 0 if self.reduced_motion else self._phase,
                         self._pointer, 0 if self.reduced_motion else self._glow)
        if self._reveal > .5:
            p.setPen(QPen(QColor(255, 255, 255, round(16 * self._reveal)), 1))
            p.drawLine(QPointF(28, 64), QPointF(self.width() - 28, 64))
            # Familiar home indicator at the foot of the expanded surface.
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 44))
            p.drawRoundedRect(QRectF(self.width() / 2 - 22, self.height() - 13, 44, 3), 1.5, 1.5)
        p.setClipping(False)
        if self.microphone_active:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#75e5b2'))
            p.drawEllipse(QPointF(self.width() - 20, 22), 3, 3)

    def _paint_listening_island(self):
        """Compact live activity; only an open capture stream enables this view."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        surface = QRectF(self.rect()).adjusted(5, 4, -5, -5)
        shape = QPainterPath()
        shape.addRoundedRect(surface, 29, 29)
        p.setClipPath(shape)
        paint_metal_shell(p, surface, 29, 0 if self.reduced_motion else self._phase,
                         self._pointer, 0 if self.reduced_motion else self._glow)
        phase = 0 if self.reduced_motion else self._phase
        glow = QRadialGradient(QPointF(self.width() - 55, 34), 80)
        glow.setColorAt(0, QColor(66, 216, 191, 38))
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillPath(shape, glow)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#75e5b2'))
        p.drawEllipse(QPointF(29, 33), 3, 3)
        font = p.font()
        font.setFamily('Segoe UI')
        font.setPixelSize(14)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor('#f5f5f7'))
        p.drawText(QRectF(43, 4, self.width() - 145, 59), Qt.AlignmentFlag.AlignVCenter, 'Listening')
        p.setPen(Qt.PenStyle.NoPen)
        for index in range(9):
            envelope = math.sin((index + 1) * math.pi / 10)
            motion = .5 + .5 * math.sin(phase * 8 + index * .8)
            height = 5 if self.reduced_motion else 4 + self.bars.level * envelope * (12 + 18 * motion)
            p.setBrush(QColor('#8cf0d5' if index < 5 else '#9eb7ff'))
            p.drawRoundedRect(QRectF(self.width() - 91 + index * 7, 33 - height / 2, 3, height), 1.5, 1.5)
        p.setClipping(False)

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
            self.eyebrow.setText('LIVE CAPTURE' if self.microphone_active else 'JUST TALK' if self.chat_only else 'AT YOUR COMMAND')
            self.privacy.setText('● Mic on' if self.microphone_active else 'Mic off')
            self.privacy.setStyleSheet('color: #75e5b2; font-size: 10px;' if self.microphone_active else 'color: #a1a1aa; font-size: 10px;')
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
