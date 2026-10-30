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
        desktop.reveal()
        dashboard = desktop.dashboard
        assert dashboard.windowTitle() == 'ZENO — Dashboard'
        deadline = time.monotonic() + 8
        while not dashboard.bridge.connected and time.monotonic() < deadline:
            QTest.qWait(20)
        assert dashboard.bridge.connected
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
    finally:
        desktop.hotkey.close()
        desktop.overlay.close()
        desktop.tray.hide()
        if desktop.dashboard:
            desktop.dashboard.hide()
            desktop.dashboard.dashboard_page.deleteLater()
        QTest.qWait(50)
