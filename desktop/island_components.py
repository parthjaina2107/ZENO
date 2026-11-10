"""Original native components informed by 21st.dev; no web runtime or remote assets."""
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


def paint_liquid_surface(p, rect, radius, hover=0.0, primary=False, quiet=False):
    """Native counterpart of the supplied LiquidButton's layered inset optics.

    Reflections are painted locally; this does not sample or blur desktop pixels.
    """
    p.save()
    shape = QPainterPath()
    shape.addRoundedRect(rect, radius, radius)
    p.setClipPath(shape, Qt.ClipOperation.IntersectClip)
    fill = QLinearGradient(rect.topLeft(), rect.bottomRight())
    if primary:
        fill.setColorAt(0, QColor('#fafbff'))
        fill.setColorAt(.48, QColor('#cdd2df'))
        fill.setColorAt(1, QColor('#e8ebf3'))
    else:
        fill.setColorAt(0, QColor(70, 73, 88, int((70 if quiet else 115) + hover * 30)))
        fill.setColorAt(.5, QColor(19, 20, 28, 235))
        fill.setColorAt(1, QColor(45, 47, 60, 215))
    p.fillPath(shape, fill)
    # Broad frosted highlight and tightly contained inner lens reflection.
    highlight = QRadialGradient(QPointF(rect.left() + rect.width() * (.22 + hover * .3), rect.top() - 12),
                                max(60, rect.width() * .8))
    highlight.setColorAt(0, QColor(255, 255, 255, int(18 + hover * 22)))
    highlight.setColorAt(1, QColor(255, 255, 255, 0))
    p.fillPath(shape, highlight)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for inset, alpha in [(1, 30), (2.5, 13), (4, 7)]:
        p.setPen(QPen(QColor(255, 255, 255, alpha), 1))
        p.drawRoundedRect(rect.adjusted(inset, inset, -inset, -inset), max(0, radius - inset), max(0, radius - inset))
    rim = QLinearGradient(rect.topLeft(), rect.bottomRight())
    rim.setColorAt(0, QColor(255, 255, 255, int(105 + hover * 45)))
    rim.setColorAt(.3, QColor(255, 255, 255, 22))
    rim.setColorAt(.7, QColor(255, 255, 255, 12))
    rim.setColorAt(1, QColor(255, 255, 255, int(90 + hover * 45)))
    p.setPen(QPen(rim, 1))
    p.drawRoundedRect(rect, radius, radius)
    p.restore()


def paint_spotlight(p, rect, radius, pointer, presence, hue=220):
    """Native GlowCard: local radial wash, colored rim bloom and white hot edge.

    The parent maps one pointer into each card, avoiding listeners or extra
    windows per control. Call before drawing content so labels remain sharp.
    """
    presence = max(0.0, min(1.0, presence))
    if presence <= .001:
        return
    p.save()
    shape = QPainterPath()
    shape.addRoundedRect(rect, radius, radius)
    color = QColor.fromHslF((hue % 360) / 360, .95, .7)
    wash = QRadialGradient(pointer, 200)
    color.setAlpha(round(26 * presence))
    wash.setColorAt(0, color)
    wash.setColorAt(1, QColor(0, 0, 0, 0))
    p.fillPath(shape, wash)
    p.setBrush(Qt.BrushStyle.NoBrush)
    # Several low-alpha strokes approximate the source's blurred outer border
    # without a blur filter or a window that intercepts mouse input.
    for width, alpha, reach in [(8, 12, 160), (5, 25, 155), (2, 210, 150), (1, 225, 95)]:
        edge = QRadialGradient(pointer, reach)
        tint = QColor('#ffffff') if width == 1 else QColor(color)
        tint.setAlpha(round(alpha * presence))
        edge.setColorAt(0, tint)
        edge.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(QPen(edge, width))
        p.drawPath(shape)
    p.restore()


def island_outline(rect, radius):
    radius = min(radius, rect.height() / 2, rect.width() / 2)
    path = QPainterPath(rect.topLeft())
    path.lineTo(rect.topRight())
    path.lineTo(rect.right(), rect.bottom() - radius)
    path.quadTo(rect.bottomRight(), QPointF(rect.right() - radius, rect.bottom()))
    path.lineTo(rect.left() + radius, rect.bottom())
    path.quadTo(rect.bottomLeft(), QPointF(rect.left(), rect.bottom() - radius))
    path.closeSubpath()
    return path


def paint_metal_shell(p, rect, radius, phase=0.0, pointer=None, presence=0.0):
    """Original Qt adaptation of Joly UI's black-center liquid-metal border.

    The reflective material stays in a narrow ring, clear of all content.
    No shader package, screen sampling or extra window is needed.
    """
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    outer = island_outline(rect, radius)
    inset = .75
    inner_rect = rect.adjusted(inset, inset, -inset, -inset)
    inner = island_outline(inner_rect, radius - inset)
    ring = outer.subtracted(inner)
    # Alternating bright and dark reflection bands give the rim its chrome depth.
    # One shared cycle travels around the full perimeter rather than reversing.
    # At the existing 33ms timer cadence this completes a lap in about 12 seconds.
    angle = (phase * .95) % math.tau
    metal = QConicalGradient(rect.center(), 35 + math.degrees(angle))
    for stop, color in [
        (0, '#bfc4d0'), (.08, '#ffffff'), (.14, '#34394b'),
        (.19, '#d8c7a5'), (.22, '#ffffff'), (.3, '#7a849c'),
        (.43, '#e8eaf0'), (.49, '#555967'), (.55, '#1d202e'),
        (.62, '#8995af'), (.67, '#ffffff'), (.71, '#d2b98e'),
        (.76, '#383d52'), (.86, '#d7dae3'), (1, '#bfc4d0'),
    ]:
        metal.setColorAt(stop, QColor(color))
    p.fillPath(ring, metal)
    # A narrow traveling reflection adds fluidity without painting a full shader.
    highlight = QRadialGradient(
        QPointF(rect.center().x() + math.cos(angle) * rect.width() * .5,
                rect.center().y() + math.sin(angle) * rect.height() * .5),
        max(70, rect.width() * .3),
    )
    highlight.setColorAt(0, QColor(255, 255, 255, 80))
    highlight.setColorAt(.35, QColor(190, 207, 242, 45))
    highlight.setColorAt(1, QColor(255, 255, 255, 0))
    p.fillPath(ring, highlight)
    if pointer is not None and presence > .001:
        reflection = QRadialGradient(pointer, 105)
        reflection.setColorAt(0, QColor(255, 255, 255, round(210 * min(1.0, presence))))
        reflection.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillPath(ring, reflection)
    ground = QLinearGradient(0, rect.top(), 0, rect.bottom())
    ground.setColorAt(0, QColor('#202022'))
    ground.setColorAt(.45, QColor('#0c0c0e'))
    ground.setColorAt(1, QColor('#030304'))
    p.fillPath(inner, ground)
    p.setBrush(Qt.BrushStyle.NoBrush)
    bevel = QLinearGradient(rect.topLeft(), rect.bottomRight())
    bevel.setColorAt(0, QColor('#b3b4ba'))
    bevel.setColorAt(.5, QColor('#55565d'))
    bevel.setColorAt(1, QColor('#a4a5ae'))
    p.setPen(QPen(bevel, .175))
    p.drawPath(outer)
    p.setPen(QPen(QColor(0, 0, 0, 180), .2))
    p.drawPath(inner)
    p.restore()


class GlassButton(QPushButton):
    def __init__(self, text, glyph=None, subtitle='', primary=False, quiet=False):
        super().__init__(text)
        self.glyph = glyph
        self.subtitle = subtitle
        self.primary = primary
        self.quiet = quiet
        self.hover = 0.0
        self.reduced_motion = False
        self.pointer = QPointF(-100, -100)
        self.presence = 0.0
        self.spotlight_hue = 220.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(56 if subtitle else 32)
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(300)
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
        if self.isEnabled():
            self._hover_to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_to(0.0)
        super().leaveEvent(event)

    def focusInEvent(self, event):
        self._hover_to(1.0)
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self._hover_to(1.0 if self.underMouse() else 0.0)
        super().focusOutEvent(event)

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
        radius = 17 if not self.subtitle else 18
        hover = self.hover if self.isEnabled() else 0.0
        paint_liquid_surface(p, rect, radius, max(hover, .5 if self.isChecked() else 0), self.primary, self.quiet)
        if self.isEnabled() and not self.reduced_motion:
            paint_spotlight(p, rect.adjusted(1, 1, -1, -1), radius - 1,
                            self.pointer, self.presence, self.spotlight_hue)
        self._paint_label(p, '#11131b' if self.primary else '#f0f1f7', 0, 1)
        if self.hasFocus():
            p.setPen(QPen(QColor('#86aaff'), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect, radius, radius)

    def _paint_label(self, p, text_color, offset, opacity, incoming=False):
        p.save()
        p.setOpacity(p.opacity() * opacity)
        p.translate(offset, 0)
        left = 14
        arrow = incoming and self.subtitle and self.width() >= 180
        right = 30 if arrow else 10
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
            p.drawText(QRectF(left, 8, self.width() - left - right, 22), Qt.AlignmentFlag.AlignVCenter, self.text())
            font.setPixelSize(10)
            font.setBold(False)
            p.setFont(font)
            p.setPen(QColor('#515766' if self.primary else '#b3b6c6'))
            p.drawText(QRectF(left, 29, self.width() - left - right, 17), Qt.AlignmentFlag.AlignVCenter, self.subtitle)
        else:
            p.drawText(QRectF(left, 0, self.width() - left - 10, self.height()), Qt.AlignmentFlag.AlignVCenter, self.text())
        if arrow:
            icon('arrow-up-right', text_color).paint(p, QRect(self.width() - 25, 11, 15, 15))
        p.restore()


def paint_voice_orb(painter, center, radius, phase=0, intensity=0):
    """Small vector aurora, rendered locally at the widget's actual scale."""
    painter.save()
    halo = QRadialGradient(center, radius * 1.6)
    halo.setColorAt(0, QColor(123, 127, 255, 75))
    halo.setColorAt(1, QColor(0, 0, 0, 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(halo)
    painter.drawEllipse(center, radius * 1.6, radius * 1.6)
    orb = QPainterPath()
    orb.addEllipse(center, radius, radius)
    painter.setClipPath(orb)
    painter.fillPath(orb, QColor('#111225'))
    for index, tint in enumerate(['#67e8f9', '#a78bfa', '#fa80b5']):
        angle = phase * .5 + index * math.tau / 3
        point = center + QPointF(math.cos(angle) * radius * .55, math.sin(angle) * radius * .55)
        light = QRadialGradient(point, radius * 1.55)
        color = QColor(tint)
        color.setAlpha(215)
        light.setColorAt(0, color)
        light.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillPath(orb, light)
    for index in range(3):
        curve = QPainterPath()
        curve.moveTo(center.x() - radius, center.y() + radius * .45)
        bend = math.sin(phase + index * .9) * radius * .25
        curve.cubicTo(center.x() - radius * .1, center.y() - radius + bend,
                      center.x() + radius * .1, center.y() + radius - bend,
                      center.x() + radius, center.y() - radius * .45 + index * 2)
        painter.setPen(QPen(QColor(242, 236, 255, 100 + round(intensity * 70)), .8))
        painter.drawPath(curve)
    painter.setClipping(False)
    painter.setPen(QPen(QColor(231, 228, 255, 100), .7))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(center, radius, radius)
    painter.restore()


class BrandMark(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(26, 26)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_voice_orb(p, QPointF(13, 13), 9)


class ActivityBars(QWidget):
    """State-aware live activity card, with measured capture levels only."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(104)
        self.level = 0.0
        self.phase = 0.0
        self.state = 'Ready'
        self.capture_active = False
        self.pointer = QPointF(-100, -100)
        self.presence = 0.0
        self.spotlight_hue = 220.0
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
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        shape = QPainterPath()
        shape.addRoundedRect(rect, 22, 22)
        p.setClipPath(shape)
        paint_liquid_surface(p, rect, 22, self.presence * .4, quiet=True)
        if not self.reduced_motion:
            paint_spotlight(p, rect, 22, self.pointer, self.presence, self.spotlight_hue)
        phase = 0 if self.reduced_motion else self.phase
        title, subtitle, tint = phase_copy(self.state, self.capture_active)
        paint_voice_orb(p, QPointF(39, 40), 20, phase, self.level if self.capture_active else 0)
        font = p.font()
        font.setFamily('Segoe UI')
        font.setPixelSize(14)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor('#f5f5f7'))
        metrics = QFontMetrics(font)
        p.drawText(76, 35, metrics.elidedText(title, Qt.TextElideMode.ElideRight, self.width() - 92))
        font.setPixelSize(10)
        font.setBold(False)
        p.setFont(font)
        p.setPen(QColor('#b1b1bd'))
        p.drawText(76, 53, QFontMetrics(font).elidedText(subtitle, Qt.TextElideMode.ElideRight, self.width() - 92))
        # A quiet dotted baseline becomes a waveform only during real capture.
        count = max(1, int((self.width() - 40) / 6))
        gap = (self.width() - 40) / count
        gradient = QLinearGradient(20, 0, self.width() - 20, 0)
        gradient.setColorAt(0, QColor('#67dcca'))
        gradient.setColorAt(.5, QColor('#a5a5fc'))
        gradient.setColorAt(1, QColor('#ed99c8'))
        p.setBrush(gradient)
        p.setPen(Qt.PenStyle.NoPen)
        for index in range(count):
            envelope = math.sin((index + 1) * math.pi / (count + 1)) ** 1.5
            activity = self.level if self.capture_active else 0
            oscillation = .35 + .65 * abs(math.sin(phase * 2 + index * .6))
            height = 2 if self.reduced_motion else 2 + 22 * envelope * activity * oscillation
            p.setOpacity(.8 if self.capture_active else .22)
            p.drawRoundedRect(QRectF(20 + index * gap, 82 - height / 2, 2.5, height), 1.25, 1.25)
        p.setOpacity(1)
        p.setClipping(False)
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(shape)
