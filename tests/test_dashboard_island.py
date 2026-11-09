"""Local dashboard integration: no microphone, provider or OS actions."""
import json
import time
from unittest.mock import MagicMock

import pytest

pytest.importorskip('PySide6.QtWebEngineCore')
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import QUrl
from desktop.dashboard import DashboardWindow, DashboardBridge, dashboard_html, STATIC
from desktop.overlay import ActivityOverlay


@pytest.mark.parametrize("busy", [False, True])
def test_exit_releases_resources_and_waits_for_active_work(tmp_path, monkeypatch, busy):
    from desktop.app import DesktopApplication
    from desktop.settings import DesktopSettings
    from PySide6.QtWidgets import QSystemTrayIcon
    qt = QApplication.instance() or QApplication([])
    monkeypatch.setattr("desktop.app.GlobalHotkey", MagicMock())
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", lambda: False)
    application = MagicMock()
    desktop = DesktopApplication(application, DesktopSettings(), tmp_path / "desktop.json")
    desktop.controller.engine = MagicMock()
    desktop.controller.stop = MagicMock()
    desktop.controller.busy = busy
    desktop.overlay.show()
    desktop.overlay.quit_button.click()
    if busy:
        desktop.controller.stop.assert_called_once()
        application.quit.assert_not_called()
        desktop.controller.busy = False
        desktop.controller.idle.emit()
    desktop.request_quit()
    application.quit.assert_called_once()
    desktop.controller.engine.close.assert_called_once()
    assert not desktop.overlay.isVisible() and not desktop.tray.isVisible()


def test_bridge_rejects_stale_approvals_and_busy_commands():
    app = QApplication.instance() or QApplication([])
    island = ActivityOverlay()
    bridge = DashboardBridge(island)
    texts, approvals, conversations = [], [], []
    bridge.conversation_requested.connect(lambda: conversations.append(True))
    island.text_requested.connect(texts.append)
    island.approval_decided.connect(lambda key, allowed: approvals.append((key, allowed)))
    try:
        bridge.send('not json')
        bridge.send('[]')
        bridge.send(json.dumps({'type': 'command', 'text': 'check battery'}))
        island.busy = True
        bridge.send(json.dumps({'type': 'command', 'text': 'second'}))
        assert texts == ['check battery']
        island.busy = False
        bridge.send(json.dumps({'type': 'command', 'text': 'open Chrome', 'mode': 'chat'}))
        assert texts[-1] == 'Chat: open Chrome'
        bridge.send(json.dumps({'type': 'listen', 'mode': 'chat'}))
        assert conversations == [True]
        island.set_approval('current', 'Review action')
        for key in ['old', 'current', 'current']:
            bridge.send(json.dumps({'type': 'permission_response', 'request_id': key, 'approved': True}))
        assert approvals == [('current', True)]
    finally:
        island.close()


def test_shared_dashboard_loads_and_routes_ui_without_server():
    app = QApplication.instance() or QApplication([])
    island = ActivityOverlay()
    dashboard = DashboardWindow(island)
    texts, stops = [], []
    island.text_requested.connect(texts.append)
    island.stop_requested.connect(lambda: stops.append(True))

    def wait_for(predicate):
        deadline = time.monotonic() + 8
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(20)
        assert predicate()

    def js(expression):
        result = []
        dashboard.dashboard_page.runJavaScript(expression, result.append)
        wait_for(lambda: bool(result))
        return result[0]

    try:
        dashboard.show()
        wait_for(lambda: dashboard.bridge.connected)
        assert not island.isVisible()
        assert js("document.getElementById('statusText').textContent") == 'Connected'
        import app_access
        quits = []
        dashboard.bridge.quit_requested.connect(lambda: quits.append("dashboard"))
        island.quit_requested.connect(lambda: quits.append("island"))
        js("document.getElementById('exitDesktop').click();true")
        wait_for(lambda: quits == ["dashboard"])
        island.quit_button.click()
        assert quits == ["dashboard", "island"]
        js("document.querySelector('[data-view=access]').click();true")
        wait_for(lambda: js("!!document.querySelector('[data-feature=gmail_send]')"))
        js("document.querySelector('[data-feature=gmail_send]').click();true")
        wait_for(lambda: not app_access.allowed("gmail_send"))
        assert app_access.allowed("gmail_read")
        js("view('workspace');true")
        island.handle_event('mail_review', '234567')
        dashboard.handle_event('mail_review', '234567')
        wait_for(lambda: js("document.getElementById('sendReviewedDraft').hidden === false"))
        js("document.getElementById('sendReviewedDraft').click();true")
        wait_for(lambda: texts == ['send draft 234567'])
        island.submit_reviewed_draft()
        assert texts == ['send draft 234567']
        texts.clear()
        assert js("!!document.querySelector('.voice-hero') && !!document.querySelector('.rail')")
        assert js("getComputedStyle(document.getElementById('mode')).pointerEvents") == 'auto'
        dashboard.handle_event('state', 'Thinking')
        assert js("document.getElementById('voiceTitle').textContent") == 'Thinking it through.'
        dashboard.handle_event('state', 'Ready')
        dashboard.handle_event('microphone', 'on')
        assert js("document.body.classList.contains('mic-active')")
        dashboard.handle_event('microphone', 'off')
        assert not js("document.body.classList.contains('mic-active')")
        js("document.getElementById('command').value='check battery'; document.getElementById('run').click(); true")
        wait_for(lambda: texts == ['check battery'])
        island.handle_event('state', 'Working')
        dashboard.handle_event('state', 'Working')
        dashboard.handle_event('transcript', 'check battery')
        assert js('runs.length') == 1
        island.set_approval('request-one', 'Review this action')
        dashboard.set_approval('request-one', 'Review this action')
        wait_for(lambda: island.request_id == 'request-one')
        assert js("document.getElementById('approval').open")
        island.collapse()
        assert island.expanded
        js("document.getElementById('approvalStop').click(); true")
        wait_for(lambda: len(stops) == 1)
        island.handle_event('state', 'Ready')
        dashboard.handle_event('state', 'Ready')
        js("document.querySelector('[data-view=activity]').click(); true")
        assert js("document.getElementById('activity').hidden") is False
        js("document.getElementById('motion').checked=true; preferences(); true")
        wait_for(lambda: island.reduced_motion)
        island.collapse()
        island.motion.setCurrentTime(island.motion.duration())
        assert island.height() == 68
        assert dashboard.isVisible()  # Island collapse never closes the dashboard.
        dashboard.handle_event('service_error', 'unavailable')
        dashboard.handle_event('state', 'Ready')
        assert js("document.getElementById('taskState').textContent") == 'AI UNAVAILABLE'
        assert js('runs[0].status') == 'failed'
        js("document.getElementById('mode').value='coding';document.getElementById('mode').dispatchEvent(new Event('change'));true")
        assert js("!document.getElementById('codingWorkspace').parentElement.hidden")
        js("document.getElementById('command').value='Solve Tutorial 3';document.getElementById('run').click();true")
        assert len(texts) == 1  # Missing project folder never dispatches a coding task.
        js("document.getElementById('codingWorkspace').value='C:/Users/HP/Desktop/etc';document.getElementById('run').click();true")
        wait_for(lambda: len(texts) == 2)
        assert texts[-1] == 'Coding task in "C:/Users/HP/Desktop/etc": Solve Tutorial 3'
        dashboard.handle_event('state', 'Ready')
        js("document.getElementById('mode').value='chat';document.getElementById('mode').dispatchEvent(new Event('change'));true")
        assert js("document.getElementById('codingWorkspace').parentElement.hidden")
        js("document.getElementById('command').value='I feel lonely';document.getElementById('run').click();true")
        wait_for(lambda: len(texts) == 3)
        assert texts[-1] == 'Chat: I feel lonely'
        dashboard.handle_event('state', 'Ready')
        js("document.getElementById('assistantProfile').value='focused';document.getElementById('applyAssistantProfile').click();true")
        wait_for(lambda: len(texts) == 4)
        assert texts[-1] == 'assistant profile focused'
        # Only known bundled assets may reach this privileged bridge page.
        assert not dashboard.dashboard_page.acceptNavigationRequest(QUrl('https://example.com'), 0, True)
        assert STATIC.as_uri() + '/glass-loop.png' in dashboard_html()
        # Material layers cannot intercept actions or obscure narrow layouts.
        assert js("getComputedStyle(document.getElementById('run'), '::before').pointerEvents") == 'none'
        assert js("getComputedStyle(document.getElementById('run')).transitionDuration") == '0s'
        js("""storage.set('zeno_motion', false);
            Object.defineProperty(systemReducedMotion, 'matches', {configurable: true, value: true});
            systemReducedMotion.dispatchEvent(new Event('change')); true""")
        assert js("document.body.classList.contains('reduce-motion') && document.getElementById('motion').checked")
        js("""preferences('language');
            Object.defineProperty(systemReducedMotion, 'matches', {configurable: true, value: false});
            systemReducedMotion.dispatchEvent(new Event('change')); true""")
        wait_for(lambda: not island.reduced_motion)
        assert not js("document.body.classList.contains('reduce-motion')")
        dashboard.setMinimumSize(0, 0)
        dashboard.resize(390, 844)
        wait_for(lambda: js('innerWidth') == 390)
        js("view('preferences'); true")
        assert js('document.documentElement.scrollWidth <= innerWidth')
        assert js("document.querySelector('.rail').getBoundingClientRect().height <= 64")
    finally:
        island.close()
        dashboard.hide()
        dashboard.dashboard_page.deleteLater()
        QTest.qWait(50)


def test_black_dashboard_owns_preferences_without_a_legacy_window(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QSystemTrayIcon, QMainWindow
    from desktop.app import DesktopApplication
    from desktop.settings import DesktopSettings
    import desktop.app as desktop_app
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(desktop_app, 'GlobalHotkey', MagicMock())
    monkeypatch.setattr(QSystemTrayIcon, 'isSystemTrayAvailable', lambda: False)
    desktop = DesktopApplication(app, DesktopSettings(), tmp_path / 'desktop.json')
    monkeypatch.setattr(desktop, 'microphones', lambda: [{'id': None, 'name': 'Default'}])
    try:
        assert not isinstance(desktop, QMainWindow)
        desktop.overlay.dashboard_button.click()
        dashboard = desktop.dashboard
        assert dashboard.windowTitle() == 'ZENO — Dashboard'
        deadline = time.monotonic() + 8
        while not dashboard.bridge.connected and time.monotonic() < deadline:
            QTest.qWait(20)
        assert dashboard.bridge.connected
        desktop.reveal()
        QTest.qWait(100)
        result = []
        dashboard.dashboard_page.runJavaScript("!document.getElementById('preferences').hidden && !!document.getElementById('saveDesktopSettings')", result.append)
        while not result and time.monotonic() < deadline:
            QTest.qWait(20)
        assert result == [True]
        desktop.handle_settings(json.dumps({'type': 'save_desktop_settings', 'shortcut': 'Ctrl+Alt+Q',
            'spoken_replies': False, 'microphone': None, 'pause_seconds': 0.9}))
        assert DesktopSettings.load(tmp_path / 'desktop.json') == DesktopSettings('Ctrl+Alt+Q', False, None, 0.9)
        desktop.controller.busy = True
        desktop.handle_settings(json.dumps({'type': 'save_desktop_settings', 'shortcut': 'F8',
            'spoken_replies': True, 'microphone': None, 'pause_seconds': 0.6}))
        assert desktop.settings.shortcut == 'Ctrl+Alt+Q'
        desktop.controller.busy = False
        desktop.open_dashboard()
        assert desktop.dashboard is dashboard
        dashboard.showMinimized()
        QTest.qWait(30)
        assert dashboard.isMinimized()
        desktop.overlay.dashboard_button.click()
        assert desktop.dashboard is dashboard and dashboard.isVisible()
        assert not dashboard.isMinimized()
        dashboard.close()
        assert not dashboard.isVisible()
        desktop.overlay.dashboard_button.click()
        assert dashboard.isVisible()
    finally:
        desktop.hotkey.close()
        desktop.overlay.close()
        desktop.tray.hide()
        if desktop.dashboard:
            desktop.dashboard.hide()
            desktop.dashboard.dashboard_page.deleteLater()
        QTest.qWait(50)


def test_workspace_construction_failure_is_visible_and_retryable(monkeypatch, tmp_path, caplog):
    from PySide6.QtWidgets import QSystemTrayIcon
    from desktop.app import DesktopApplication
    from desktop.settings import DesktopSettings
    import desktop.app as desktop_app
    import desktop.dashboard as dashboard_module
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(desktop_app, 'GlobalHotkey', MagicMock())
    monkeypatch.setattr(QSystemTrayIcon, 'isSystemTrayAvailable', lambda: False)
    desktop = DesktopApplication(app, DesktopSettings(), tmp_path / 'desktop.json')
    monkeypatch.setattr(desktop, 'microphones', lambda: [{'id': None, 'name': 'Default'}])
    constructor = dashboard_module.DashboardWindow
    monkeypatch.setattr(dashboard_module, 'DashboardWindow', MagicMock(side_effect=RuntimeError('Synthetic load failure')))
    try:
        desktop.overlay.dashboard_button.click()
        assert desktop.dashboard is None
        assert desktop.overlay.expanded
        assert 'workspace could not open' in desktop.overlay.caption.text()
        assert 'Could not open the workspace' in caplog.text
        monkeypatch.setattr(dashboard_module, 'DashboardWindow', constructor)
        desktop.overlay.dashboard_button.click()
        assert desktop.dashboard is not None and desktop.dashboard.isVisible()
    finally:
        desktop.hotkey.close()
        desktop.overlay.close()
        desktop.tray.hide()
        if desktop.dashboard:
            desktop.dashboard.hide()
            desktop.dashboard.dashboard_page.deleteLater()
        QTest.qWait(50)
