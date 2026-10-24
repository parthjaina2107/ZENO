"""Transient, non-activating status display; no microphone or task ownership."""
import math

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QColor, QCursor, QPainter, QLinearGradient, QPen
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget


class ActivityBars(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self.level = 0.0
        self.phase = 0
        self.state = "Ready"
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.tick)
        self.setAccessibleName("Microphone level while listening; progress animation otherwise")

    def tick(self):
        self.phase += 0.2
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        for index in range(19):
            envelope = 0.35 + 0.65 * math.sin((index + 1) * math.pi / 20)
            activity = self.level if self.state == "Listening" else (
                0 if self.state == "Ready" else 0.3 + 0.2 * math.sin(self.phase + index * 0.45))
            height = 4 + 26 * envelope * activity
            bar = QRectF(self.width() / 2 - 92 + index * 10, (34 - height) / 2, 5, height)
            painter.setBrush(QColor(216, 224, 230, 210))
            painter.drawRoundedRect(bar, 2.5, 2.5)


class ActivityOverlay(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.WindowDoesNotAcceptFocus
                         | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(400, 180)
        self.setAccessibleName("ZENO activity")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        self.title = QLabel("ZENO")
        self.bars = ActivityBars(self)
        self.caption = QLabel("Press your shortcut again to stop")
        for label in (self.title, self.caption):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("color: #d7dbdf; background: transparent; font-size: 13px;")
        self.title.setStyleSheet("color: #eef0f2; background: transparent; font-size: 12px; font-weight: 500;")
        layout.addWidget(self.title)
        layout.addWidget(self.bars)
        layout.addWidget(self.caption)
        self.dismiss = QTimer(self)
        self.dismiss.setSingleShot(True)
        self.dismiss.timeout.connect(self.hide)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        surface = QRectF(self.rect()).adjusted(10, 8, -10, -12)
        painter.setPen(Qt.PenStyle.NoPen)
        # Layered shadow stays inside the translucent window's bounds.
        for spread in range(6, 0, -1):
            painter.setBrush(QColor(0, 0, 0, 5))
            painter.drawRoundedRect(surface.adjusted(-spread, -spread + 3, spread, spread + 3), 22 + spread, 22 + spread)
        glass = QLinearGradient(0, surface.top(), 0, surface.bottom())
        glass.setColorAt(0, QColor(55, 59, 64, 222))
        glass.setColorAt(1, QColor(34, 38, 43, 222))
        painter.setBrush(glass)
        painter.drawRoundedRect(surface, 22, 22)
        rim = QLinearGradient(0, surface.top(), 0, surface.bottom())
        rim.setColorAt(0, QColor(255, 255, 255, 65))
        rim.setColorAt(1, QColor(255, 255, 255, 20))
        painter.setPen(QPen(rim, 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(surface, 22, 22)

    def handle_event(self, kind, value):
        if kind == "state":
            self.dismiss.stop()
            self.bars.state = value
            self.bars.level = 0
            self.title.setText("ZENO · " + value)
            if value == "Preparing":
                self.caption.setText("Press your shortcut again to stop")
                screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
                area = screen.availableGeometry()
                self.move(area.center().x() - self.width() // 2, area.bottom() - self.height() - 24)
            if value == "Ready":
                self.bars.timer.stop()
                self.dismiss.start(4000)
            else:
                self.bars.timer.start()
                self.show()
            self.bars.update()
        elif kind == "level" and self.bars.state == "Listening":
            self.bars.level = max(0.0, min(1.0, float(value)))
        elif kind in {"transcript", "reply"}:
            self.caption.setText(value[:150] + ("…" if len(value) > 150 else ""))

    def hideEvent(self, event):
        self.bars.timer.stop()
        super().hideEvent(event)
