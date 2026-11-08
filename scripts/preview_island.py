"""Render the actual native island with synthetic events; no device/provider access.

Run with the project interpreter: python scripts/preview_island.py
"""
import os
import argparse
from pathlib import Path
import sys
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QCursor, QFont, QFontDatabase, QImage, QLinearGradient, QPainter
from PySide6.QtWidgets import QApplication
from desktop.overlay import ActivityOverlay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spotlight', action='store_true', help='Render synthetic cursor spotlight examples')
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    # Windows' offscreen Qt plugin does not enumerate system fonts itself.
    font_dir = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    for name in ('segoeui.ttf', 'seguisb.ttf', 'segoeuib.ttf'):
        if (font_dir / name).is_file():
            QFontDatabase.addApplicationFont(str(font_dir / name))
    island = ActivityOverlay()
    island.reduced_motion = True

    def capture():
        island.show()
        island.motion.setCurrentTime(island.motion.duration())
        app.processEvents()
        island.ambient.stop()
        island.dismiss.stop()
        island.bars.timer.stop()
        return island.grab().toImage()

    try:
        if args.spotlight:
            island.expand()
            island.motion.setCurrentTime(island.motion.duration())
            canvas = QImage(2240, 2160, QImage.Format.Format_ARGB32_Premultiplied)
            canvas.setDevicePixelRatio(2)
            canvas.fill(QColor('#1c1e26'))
            painter = QPainter(canvas)
            painter.setPen(QColor('#f5f5f7'))
            painter.setFont(QFont('Segoe UI', 26, QFont.Weight.DemiBold))
            painter.drawText(54, 68, 'A spotlight that follows your lead.')
            painter.setFont(QFont('Segoe UI', 11))
            painter.setPen(QColor('#b0b0bc'))
            painter.drawText(54, 97, 'ZENO / Native GlowCard adaptation / Simulated pointer positions')
            renders = []
            for label, point, reduced, x, y in [
                ('01   CHROME SHELL + VOICE CARD', QPoint(420, 82), False, 40, 166),
                ('02   COLOR FOLLOWS POSITION', QPoint(30, 155), False, 600, 166),
                ('03   QUICK-ACTION SPOTLIGHT', QPoint(210, 310), False, 40, 622),
                ('04   REDUCED MOTION', QPoint(210, 310), True, 600, 622),
            ]:
                island.reduced_motion = reduced
                with patch.object(QCursor, 'pos', return_value=island.mapToGlobal(point)):
                    for _ in range(60):
                        island._track_pointer()
                    frame = capture()
                renders.append(frame)
                painter.setPen(QColor('#b0b0bc'))
                painter.setFont(QFont('Segoe UI', 9))
                painter.drawText(x + 24, y - 18, label)
                painter.drawImage(QPoint(x, y), frame)
            assert renders[0] != renders[1], 'Pointer positions must produce different lighting'
            assert island.bars.presence == 0 and island.type_button.presence == 0
            painter.setFont(QFont('Segoe UI', 9))
            painter.drawText(54, 1050, 'Actual native Qt renders · no device or provider access · reduced motion disables spotlight')
            painter.end()
            target = ROOT / 'docs/island-spotlight-preview.png'
            if not canvas.save(str(target)):
                raise RuntimeError('Could not save spotlight preview')
            print(target)
            return
        compact = capture()
        island.expand()
        expanded = capture()
        island.handle_event('state', 'Listening')
        island.handle_event('microphone', 'on')
        island.reduced_motion = False
        island.bars.reduced_motion = False
        island.handle_event('level', '0.72')
        listening = capture()
        island.handle_event('state', 'Ready')
        island.reduced_motion = True
        island.handle_event('state', 'Approval needed')
        island.set_approval('synthetic-preview', 'Move the selected files to the archive?\nReview the action before ZENO continues.')
        approval = capture()

        scale = 2
        canvas = QImage(1120 * scale, 850 * scale, QImage.Format.Format_ARGB32_Premultiplied)
        canvas.setDevicePixelRatio(scale)
        canvas.fill(QColor('#17191f'))
        p = QPainter(canvas)
        background = QLinearGradient(0, 0, 1120, 850)
        background.setColorAt(0, QColor('#272932'))
        background.setColorAt(1, QColor('#15161b'))
        p.fillRect(QRectF(0, 0, 1120, 850), background)
        p.setPen(QColor('#f5f5f7'))
        p.setFont(QFont('Segoe UI', 26, QFont.Weight.DemiBold))
        p.drawText(54, 68, 'A little space. A lot of possibility.')
        p.setFont(QFont('Segoe UI', 11))
        p.setPen(QColor('#b0b0bc'))
        p.drawText(54, 97, 'ZENO  /  Native Dynamic Island')
        for label, image, x, y in [
            ('01   ALWAYS WITHIN REACH', compact, 68, 165),
            ('02   LIVE LISTENING', listening, 632, 165),
            ('03   ROOM FOR YOUR NEXT IDEA', expanded, 40, 322),
            ('04   YOUR ACTION. YOUR CALL.', approval, 600, 322),
        ]:
            p.setPen(QColor('#b0b0bc'))
            p.setFont(QFont('Segoe UI', 9))
            p.drawText(x + 24, y - 20, label)
            p.drawImage(QPoint(x, y), image)
        p.setPen(QColor('#92929e'))
        p.setFont(QFont('Segoe UI', 9))
        p.drawText(54, 813, 'Actual Qt renders · synthetic preview events · no microphone or AI service used')
        p.end()
        target = ROOT / 'docs/island-21st-preview.png'
        if not canvas.save(str(target)):
            raise RuntimeError('Could not save island preview')
        print(target)
    finally:
        island.lights.close()
        island.close()


if __name__ == '__main__':
    main()
