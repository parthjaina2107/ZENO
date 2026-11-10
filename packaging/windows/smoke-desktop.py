from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from desktop.app import DesktopApplication, run_desktop
import sys
assert Path(sys.base_prefix).resolve().is_relative_to(Path('runtime').resolve())
init = DesktopApplication.__init__
ready = []
def open_workspace(host, *args):
    init(host, *args)
    host.open_dashboard()
    def check():
        if host.dashboard.bridge.connected and host.dashboard.isVisible():
            image = host.dashboard.grab().toImage()
            if image.isNull():
                QTimer.singleShot(100, check)
                return
            ready.append(True)
            host.request_quit()
        else:
            QTimer.singleShot(100, check)
    QTimer.singleShot(100, check)
    QTimer.singleShot(30000, QApplication.instance().quit)
DesktopApplication.__init__ = open_workspace
assert run_desktop() == 0 and ready
