"""Offline dashboard layout checks and desktop snapshots; no submitted requests.

Requires the existing desktop environment and Microsoft Edge on Windows. The
renderer uses a separate ignored profile under scratch/liquid-ui, never a user's
browser session. Phone widths are checked in Qt; desktop snapshots use Edge.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QUrl
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from desktop.dashboard import DashboardWindow, STATIC
from desktop.overlay import ActivityOverlay


def main():
    app = QApplication.instance() or QApplication([])
    for name in ('segoeui.ttf', 'seguisb.ttf', 'segoeuib.ttf'):
        font = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / name
        if font.is_file():
            QFontDatabase.addApplicationFont(str(font))
    island = ActivityOverlay()
    dashboard = DashboardWindow(island)
    output = ROOT / 'scratch/liquid-ui'
    output.mkdir(parents=True, exist_ok=True)

    def wait_for(predicate):
        deadline = time.monotonic() + 10
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(20)
        if not predicate():
            raise RuntimeError('UI did not finish loading')

    def js(code):
        result = []
        dashboard.dashboard_page.runJavaScript(code, result.append)
        wait_for(lambda: bool(result))
        return result[0]

    browser = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
    if not browser.is_file():
        raise RuntimeError('Preview screenshots require Microsoft Edge on Windows')

    def strip_scripts(html):
        # Parse an inert document, without attaching any supplied nodes to the page.
        import json
        return js("(() => { const doc = new DOMParser().parseFromString(" +
                  json.dumps(html) + ", 'text/html'); doc.querySelectorAll('script').forEach(s => s.remove());" +
                  "return doc.documentElement.outerHTML; })()")

    def capture(name, html=None):
        # Freeze the actual DOM. Edge's headless renderer avoids Windows Qt's
        # offscreen compositor retaining stale frames. No application script,
        # authentication, device access or network request runs in this renderer.
        if html is None:
            html = js('document.documentElement.outerHTML')
        html = strip_scripts(html)
        html = html.replace('</body>', '<script>for (const d of document.querySelectorAll("dialog[open]")) {d.close();d.showModal();}</script></body>')
        source = output / (name + '.html')
        source.write_text(html, encoding='utf-8')
        target = output / (name + '.png')
        result = subprocess.run([
            str(browser), '--headless', '--disable-gpu', '--no-first-run',
            '--no-default-browser-check', '--force-device-scale-factor=1',
            '--user-data-dir=' + str(output / 'edge-profile'),
            '--window-size=' + str(dashboard.width()) + ',' + str(dashboard.height()),
            '--screenshot=' + str(target), '--virtual-time-budget=600', source.as_uri(),
        ], capture_output=True, timeout=30, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode or not target.is_file():
            raise RuntimeError('Could not render ' + name + ': ' + result.stderr.decode(errors='replace')[-500:])
        print(target)

    def no_horizontal_overflow():
        assert js('document.documentElement.scrollWidth <= innerWidth'), 'Horizontal overflow'

    try:
        dashboard.resize(1400, 1080)
        dashboard.show()
        wait_for(lambda: dashboard.bridge.connected)
        wait_for(lambda: js("document.getElementById('statusText').textContent === 'Connected' && !!document.querySelector('svg.lucide')"))
        js("document.body.classList.add('reduce-motion'); true")
        no_horizontal_overflow()
        assert js("getComputedStyle(document.getElementById('run'), '::before').pointerEvents") == 'none'
        capture('workspace')
        # No requests are submitted; sample events exercise existing presentation.
        js("view('preferences'); true")
        no_horizontal_overflow()
        capture('preferences')
        js("view('activity'); true")
        capture('activity')
        js("view('workspace'); true")
        dashboard.set_approval('synthetic-preview', 'Move the selected files to the archive? Review this action before continuing.')
        wait_for(lambda: js("document.getElementById('approval').open"))
        capture('approval')
        dashboard.set_approval('', '')
        # Exercise the same shared styles at phone width, independent of the
        # native dashboard's normal minimum window size.
        dashboard.setMinimumSize(0, 0)
        dashboard.resize(390, 844)
        QTest.qWait(200)
        no_horizontal_overflow()
        assert js("document.querySelector('.rail').getBoundingClientRect().height <= 64")
        js("view('preferences'); true")
        no_horizontal_overflow()
        # Load the browser document with scripts disabled: no auth, sockets or
        # device actions. This also checks its normal external stylesheet path.
        dashboard.resize(1400, 1080)
        html = (ROOT / 'server/templates/index.html').read_text(encoding='utf-8')
        html = strip_scripts(html)
        for name in ('app.css', 'liquid-glass.css'):
            css = (STATIC / name).read_text(encoding='utf-8')
            css = re.sub(r'@import\s+url\([^;]+;', '', css)
            html = html.replace(f'<link rel="stylesheet" href="/static/{name}" />', '<style>' + css + '</style>')
        icons = (STATIC / 'vendor/lucide.min.js').read_text(encoding='utf-8')
        html = html.replace('</body>', '<script>' + icons + ';lucide.createIcons();</script></body>')
        dashboard.dashboard_page.setHtml(html, QUrl('about:blank'))
        wait_for(lambda: js("!!document.querySelector('svg.lucide-eye')"))
        js("document.getElementById('auth').showModal(); true")
        capture('browser-sign-in')
        html = (ROOT / 'server/templates/audit.html').read_text(encoding='utf-8')
        html = strip_scripts(html)
        css = (STATIC / 'liquid-glass.css').read_text(encoding='utf-8')
        html = html.replace('<link rel="stylesheet" href="/static/liquid-glass.css" />', '<style>' + css + '</style>')
        html = html.replace('Loading the latest 100 events…', 'Preview · no audit data loaded')
        capture('audit', html)
        print('Desktop/mobile overflow and decorative-layer interaction checks passed.')
    finally:
        island.close()
        island.lights.close()
        dashboard.hide()
        dashboard.dashboard_page.deleteLater()
        QTest.qWait(50)


if __name__ == '__main__':
    main()
