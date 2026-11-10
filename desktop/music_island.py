"""Native now-playing surface for the desktop island."""
import math

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QPushButton, QWidget


class MusicIsland(QWidget):
    command = Signal(str)
    assistant = Signal()
    exit = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.playback = None
        self.cover = QPixmap()
        self.cover_bytes = None
        self.large = False
        self.buttons = {}
        for name, glyph in [('Previous', '\ue100'), ('Pause', '\ue103'), ('Next', '\ue101'),
                            ('Assistant', '\ue720'), ('Exit ZENO', '\ue8bb')]:
            button = QPushButton(glyph, self)
            button.setToolTip(name)
            button.setAccessibleName(name)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet("QPushButton{font:18px 'Segoe MDL2 Assets'; color:#f6f6f8;"
                                 "background:transparent;border:0;border-radius:12px}"
                                 "QPushButton:hover,QPushButton:focus{background:#29292b}"
                                 "QPushButton:disabled{color:#48484b}")
            self.buttons[name] = button
        for name in ('Previous', 'Next'):
            self.buttons[name].clicked.connect(lambda checked=False, n=name: self.command.emit(n.lower()))
        self.buttons['Pause'].clicked.connect(self.toggle)
        self.buttons['Assistant'].clicked.connect(self.assistant.emit)
        self.buttons['Exit ZENO'].clicked.connect(self.exit.emit)

    def toggle(self):
        if self.playback:
            self.command.emit('pause' if self.playback[2] else 'play')

    def configure(self, playback, large):
        self.playback = playback
        self.large = large
        title, artist, playing, position, duration = playback[:5]
        artwork, controls = playback[5:7] if len(playback) > 5 else (None, (True,) * 4)
        if artwork != self.cover_bytes:
            self.cover_bytes = artwork
            self.cover = QPixmap()
            if artwork:
                self.cover.loadFromData(artwork)
        toggle = self.buttons['Pause']
        toggle.setText('\ue103' if playing else '\ue102')
        toggle.setAccessibleName('Pause' if playing else 'Play')
        toggle.setToolTip(toggle.accessibleName())
        for name, enabled in zip(('Previous', 'Pause', 'Next'), (controls[0], controls[1 if playing else 2], controls[3])):
            self.buttons[name].setEnabled(enabled)
        for button in self.buttons.values():
            button.setVisible(large or button is self.buttons['Exit ZENO'])
        self.setAccessibleName(f"{'Playing' if playing else 'Paused'} {title}, {artist}")
        w = self.width()
        for name, x in [('Assistant', 12), ('Previous', w // 2 - 68), ('Pause', w // 2 - 18),
                        ('Next', w // 2 + 32), ('Exit ZENO', w - 48)]:
            self.buttons[name].setGeometry(x, 102 if large else 15, 36, 32)
        self.update()

    def paintEvent(self, event):
        if not self.playback:
            return
        title, artist, playing, position, duration = self.playback[:5]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w = self.width()
        size = 46 if self.large else 34
        x, y = (18, 13) if self.large else (14, 12)
        tile = QRectF(x, y, size, size)
        clip = QPainterPath()
        clip.addRoundedRect(tile, 8, 8)
        p.save()
        p.setClipPath(clip)
        if not self.cover.isNull():
            side = min(self.cover.width(), self.cover.height())
            p.drawPixmap(tile, self.cover, QRectF((self.cover.width()-side)/2, (self.cover.height()-side)/2, side, side))
        else:
            gradient = QLinearGradient(tile.topLeft(), tile.bottomRight())
            gradient.setColorAt(0, QColor('#ff9163'))
            gradient.setColorAt(1, QColor('#a72f60'))
            p.fillRect(tile, gradient)
            font = p.font()
            font.setPixelSize(size // 2)
            p.setFont(font)
            p.setPen(Qt.GlobalColor.white)
            p.drawText(tile, Qt.AlignmentFlag.AlignCenter, '♫')
        p.restore()

        def label(rect, text, pixels, color, bold=False, right=False):
            font = p.font()
            font.setPixelSize(pixels)
            font.setBold(bold)
            p.setFont(font)
            p.setPen(QColor(color))
            shown = p.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, int(rect.width()))
            align = Qt.AlignmentFlag.AlignRight if right else Qt.AlignmentFlag.AlignLeft
            p.drawText(rect, align | Qt.AlignmentFlag.AlignVCenter, shown)

        left = x + size + 10
        wave_x = w - (44 if self.large else 76)
        label(QRectF(left, y, wave_x-left-6, size/2+3), title, 15 if self.large else 13, '#fafafa', True)
        label(QRectF(left, y+size/2, wave_x-left-6, size/2), artist or ('Playing' if playing else 'Paused'), 12, '#a5a5aa')
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#dbada1'))
        phase = self.parentWidget()._phase if playing and not self.parentWidget().reduced_motion else 0
        for i, base in enumerate((6, 13, 19, 11, 6)):
            h = base * (.7 + .3 * math.sin(phase*7+i)) if playing else 3
            p.drawRoundedRect(QRectF(wave_x+i*4, y+size/2-h/2, 2.5, h), 1.25, 1.25)
        if duration:
            stamp = lambda t: f'{t//60}:{t%60:02d}'
            bar_y = 72 if self.large else 49
            margin = 18 if self.large else left
            end = w-18 if self.large else wave_x+18
            if not self.large:
                label(QRectF(margin, bar_y-7, 43, 14), stamp(position), 9, '#a5a5aa')
                label(QRectF(end-43, bar_y-7, 43, 14), '−'+stamp(duration-position), 9, '#a5a5aa', right=True)
                margin += 38
                end -= 39
            p.setPen(Qt.PenStyle.NoPen)
            for width, color in ((end-margin, '#363638'), ((end-margin)*position/duration, '#dddde0')):
                p.setBrush(QColor(color))
                p.drawRoundedRect(QRectF(margin, bar_y-1, width, 3), 1.5, 1.5)
            if self.large:
                label(QRectF(margin, 78, 70, 16), stamp(position), 11, '#aaaaaf')
                label(QRectF(end-70, 78, 70, 16), '−'+stamp(duration-position), 11, '#aaaaaf', right=True)
