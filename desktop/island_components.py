"""Native motion components inspired by OriginKit; no web runtime or remote assets."""
import math
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QRect, QSize, QPointF, QVariantAnimation, QEasingCurve, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QLinearGradient, QRadialGradient, QConicalGradient, QPainterPath, QPixmap, QIcon, QFontMetrics
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QPushButton, QWidget
from .presentation import phase_copy

ICONS = Path(__file__).parent / 'assets/icons'
_icons = {}


def icon(name, color='#c6d1e5'):
    key = (name, color)
    if key not in _icons:
        svg = (ICONS / (name + '.svg')).read_text(encoding='utf-8').replace('currentColor', color)
        renderer = QSvgRenderer(svg.encode())
        pixmap = QPixmap(48, 48)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        _icons[key] = QIcon(pixmap)
    return _icons[key]


class GlassButton(QPushButton):
    def __init__(self, text, glyph=None, subtitle='', primary=False, quiet=False):
        super().__init__(text)
        self.glyph = glyph
        self.subtitle = subtitle
        self.primary = primary
        self.quiet = quiet
        self.hover = 0.0
        self.reduced_motion = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(56 if subtitle else 32)
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(170)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self._hover_changed)

    def _hover_changed(self, value):
        self.hover = float(value)
        self.update()

    def _hover_to(self, target):
        self.animation.stop()
        if self.reduced_motion:
            self._hover_changed(target)
            return
        self.animation.setStartValue(self.hover)
        self.animation.setEndValue(target)
        self.animation.start()

    def enterEvent(self, event):
        self._hover_to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_to(0.0)
        super().leaveEvent(event)

    def sizeHint(self):
        font = self.font()
        font.setFamily('Segoe UI')
        font.setPixelSize(11)
        width = QFontMetrics(font).horizontalAdvance(self.text()) + 28 + (25 if self.glyph else 0)
        return QSize(150 if self.subtitle else max(70, width), 56 if self.subtitle else 34)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(.38)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if self.isDown():
            rect.translate(0, 1)
        if self.primary:
            fill = QLinearGradient(0, 0, 0, self.height())
            fill.setColorAt(0, QColor('#f5f8ff'))
            fill.setColorAt(1, QColor('#c7d8ed' if self.hover < .5 else '#eef5ff'))
            text_color = '#111825'
        else:
            fill = QColor(255, 255, 255, int((5 if self.quiet else 10) + self.hover * 14))
            text_color = '#e3eaf6' if not self.quiet else '#a2aec3'
        p.setBrush(fill)
        p.setPen(QPen(QColor('#86aaff') if self.hasFocus() else QColor(185, 209, 255, int(20 + self.hover * 40)), 1))
        p.drawRoundedRect(rect, 12, 12)
        left = 14
        if self.glyph:
            size = 20 if self.subtitle else 15
            y = 13 if self.subtitle else (self.height() - size) // 2
            icon(self.glyph, text_color).paint(p, QRect(left, y, size, size))
            left += size + 10
        font = p.font()
        font.setFamily('Segoe UI')
        font.setPixelSize(12 if self.subtitle else 11)
        font.setBold(self.primary or bool(self.subtitle))
        p.setFont(font)
        p.setPen(QColor(text_color))
        if self.subtitle:
            p.drawText(QRectF(left, 8, self.width() - left - 10, 22), Qt.AlignmentFlag.AlignVCenter, self.text())
            font.setPixelSize(10)
            font.setBold(False)
            p.setFont(font)
            p.setPen(QColor('#7e8ca6'))
            p.drawText(QRectF(left, 29, self.width() - left - 10, 17), Qt.AlignmentFlag.AlignVCenter, self.subtitle)
        else:
            p.drawText(QRectF(left, 0, self.width() - left - 10, self.height()), Qt.AlignmentFlag.AlignVCenter, self.text())


class BrandMark(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(26, 26)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        glass = QLinearGradient(3, 1, 23, 26)
        for stop, color in [(0, '#c1ebee'), (.25, '#477d9d'), (.55, '#18243c'), (.8, '#9e90d3'), (1, '#dfeafa')]:
            glass.setColorAt(stop, QColor(color))
        p.setPen(QPen(QColor('#c1d5eb'), .7))
        p.setBrush(glass)
        p.drawEllipse(QRectF(3, 3, 20, 20))
        p.setBrush(QColor('#0c1120'))
        p.setPen(QPen(QColor('#647ca0'), 1))
        p.drawEllipse(QRectF(8, 8, 10, 10))


class ActivityBars(QWidget):
    """Live level card with low-cost ribbon and pointer-field motion."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(88)
        self.level = 0.0
        self.phase = 0.0
        self.state = 'Ready'
        self.capture_active = False
        self.pointer = QPointF(-100, -100)
        self.presence = 0.0
        self.reduced_motion = False
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.tick)
        self.setAccessibleName('Voice status and measured microphone level')

    def tick(self):
        if not self.reduced_motion:
            self.phase += .12
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        shape = QPainterPath()
        shape.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 16, 16)
        p.setClipPath(shape)
        p.fillPath(shape, QColor('#0b1220'))
        phase = 0 if self.reduced_motion else self.phase
        for layer, tint in enumerate(['#459ed4', '#657ee3', '#a283da']):
            path = QPainterPath()
            offset = math.sin(phase + layer) * 5
            path.moveTo(-20, 80 + layer * 6)
            path.cubicTo(self.width() * .36, 85 + offset, self.width() * .56, -25 + offset,
                         self.width() + 20, 5 + layer * 6)
            for width, alpha in [(22, 5), (10, 8), (2, 30)]:
                color = QColor(tint)
                color.setAlpha(alpha + (round(self.level * 20) if self.state == 'Listening' else 0))
                p.setPen(QPen(color, width))
                p.drawPath(path)
        for row in range(4):
            for col in range(22):
                point = QPointF(12 + col * 20, 10 + row * 22)
                distance = math.hypot(point.x() - self.pointer.x(), point.y() - self.pointer.y())
                ring = max(0, 1 - abs(distance - 55) / 24) * self.presence
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(135, 194, 219, int(8 + ring * 80)))
                p.drawEllipse(point, 1, 1)
        title, subtitle, tint = phase_copy(self.state, self.capture_active)
        center = QPointF(34, 43)
        pulse = 0 if self.reduced_motion or self.state == 'Ready' else math.sin(phase * 1.8) * 1.3
        radius = 17 + pulse + (self.level * 2 if self.capture_active else 0)
        halo = QRadialGradient(center, 29)
        glow = QColor(tint)
        glow.setAlpha(65 if self.capture_active else 32)
        halo.setColorAt(0, glow)
        halo.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(halo)
        p.drawEllipse(center, 29, 29)
        core = QRadialGradient(QPointF(29, 37), 30)
        core.setColorAt(0, QColor('#e6f6ff'))
        core.setColorAt(.22, QColor(tint))
        core.setColorAt(.65, QColor('#253c57'))
        core.setColorAt(1, QColor('#080e18'))
        p.setBrush(core)
        p.drawEllipse(center, radius, radius)
        rim = QConicalGradient(center, phase * 40)
        for stop, color in [(0, tint), (.3, '#c1a4ed'), (.55, '#578ca4'), (.8, '#d4e9ee'), (1, tint)]:
            rim.setColorAt(stop, QColor(color))
        p.setPen(QPen(rim, 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(center, radius + 3.5, radius + 3.5)
        font = p.font()
        font.setFamily('Segoe UI')
        font.setPixelSize(13)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor('#e7edf9'))
        p.drawText(66, 37, title)
        font.setPixelSize(10)
        font.setBold(False)
        p.setFont(font)
        p.setPen(QColor('#8a9bb7'))
        p.drawText(66, 56, subtitle)
        for index in range(15):
            envelope = .3 + .7 * math.sin((index + 1) * math.pi / 16)
            activity = self.level if self.capture_active else 0 if self.state == 'Ready' else .2 + .1 * math.sin(phase + index * .4)
            height = 3 + 29 * envelope * activity
            p.setBrush(QColor('#9ad9e5' if self.state == 'Listening' else '#657894'))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(self.width() - 105 + index * 5, (88 - height) / 2, 2.5, height), 1.2, 1.2)
        p.setClipping(False)
        p.setPen(QPen(QColor(99, 121, 154, 56), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(shape)
