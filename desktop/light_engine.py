"""Input-transparent screen-edge lighting, active only during actual mic capture."""
import math
import time

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget


class MicrophoneLights(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAccessibleName('ZENO microphone active light')
        self.setWindowTitle('ZENO - Microphone light')
        self.active = False
        self.reduced_motion = False
        self.level = 0.0
        self.started = 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.update)

    def set_active(self, active, screen=None, reduced_motion=False):
        self.reduced_motion = reduced_motion
        if not active:
            self.active = False
            self.timer.stop()
            self.hide()
            self.level = 0.0
            return
        if self.active:
            return
        self.active = True
        self.started = time.monotonic()
        if screen:
            self.setGeometry(screen.geometry())
        self.show()
        if not self.reduced_motion:
            self.timer.start()
        self.update()

    def paintEvent(self, event):
        if not self.active:
            return
        elapsed = time.monotonic() - self.started
        pulse = 1.0 if self.reduced_motion else 0.72 + 0.14 * math.sin(elapsed * 2.4) + self.level * 0.2
        entrance = 0 if self.reduced_motion else max(0.0, 1.0 - elapsed / 0.85)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for width, alpha in [(28 + entrance * 22, 8), (16, 14), (7, 36), (2, 165)]:
            rim = QLinearGradient(QPointF(0, 0), QPointF(self.width(), self.height() * .4))
            for stop, color in [(0, '#54dcca'), (.35, '#91cfff'), (.68, '#aa8bff'), (1, '#efb18e')]:
                tint = QColor(color)
                tint.setAlpha(min(255, round(alpha * pulse)))
                rim.setColorAt(stop, tint)
            painter.setPen(QPen(rim, width))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(2, 2, -2, -2), 22, 22)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)
