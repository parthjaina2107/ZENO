"""The single desktop dashboard, with a local-only bridge."""
import json
import re
from pathlib import Path

import app_access
import psutil
from PySide6.QtCore import QObject, Signal, Slot, QUrl, Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineUrlRequestInterceptor
from PySide6.QtWebEngineWidgets import QWebEngineView


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "server" / "static"


def dashboard_html():
    """Reuse the real dashboard markup, styles, scripts and artwork without a server."""
    html = (ROOT / "server/templates/index.html").read_text(encoding="utf-8")
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    css = re.sub(r'@import\s+url\([^;]+;', '', css)
    css = css.replace('/static/', STATIC.as_uri() + '/')
    html = html.replace('<link rel="stylesheet" href="/static/app.css" />', '<!-- shared-style -->')
    html = html.replace('/static/', STATIC.as_uri() + '/')
    html = html.replace('<!-- shared-style -->', '<style>' + css + '</style>')
    html = html.replace('<body>', '<body class="desktop-island">')
    # Deferred scripts retain their order; app.js receives qt.webChannelTransport.
    html = html.replace('<script defer', '<script defer src="qrc:///qtwebchannel/qwebchannel.js"></script><script defer', 1)
    extra = (STATIC / "island.css").read_text(encoding="utf-8")
    liquid = (STATIC / "liquid-glass.css").read_text(encoding="utf-8")
    html = html.replace('<link rel="stylesheet" href="' + STATIC.as_uri() + '/liquid-glass.css" />', '')
    preferences = (ROOT / 'desktop/preferences.html').read_text(encoding='utf-8')
    html = html.replace('<div class="settings glass">', preferences + '<div class="settings glass">', 1)
    html = html.replace('</nav>', '<button class="nav" data-view="access"><i data-lucide="shield-check"></i>App access</button></nav>', 1)
    html = html.replace('</main>', """
        <section class="view" id="access" hidden>
          <div class="page-heading"><div><h1>App access</h1>
          <p>Choose which tools ZENO can use on this computer.</p></div></div>
          <p role="status" id="accessStatus"></p><div id="accessGroups"></div>
        </section></main>""", 1)
    return html.replace('</head>', '<style>' + extra + '\n' + liquid + '</style></head>')


class LocalAssetsOnly(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info):
        url = info.requestUrl()
        allowed = {STATIC / 'app.js', STATIC / 'glass-loop.png', STATIC / 'vendor/lucide.min.js'}
        local = url.isLocalFile() and Path(url.toLocalFile()).resolve() in allowed
        internal = url.scheme() in {'data', 'about'} or url.toString() == 'qrc:///qtwebchannel/qwebchannel.js'
        info.block(not (local or internal))


class DashboardPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, kind, main_frame):
        # The bridge belongs only to bundled UI, never an external page.
        return url.scheme() in {'data', 'about'}


class DashboardBridge(QObject):
    event = Signal(str)
    settings_request = Signal(str)
    quit_requested = Signal()
    capture_changed = Signal(bool)
    conversation_requested = Signal()

    def __init__(self, island):
        super().__init__(island)
        self.island = island
        self.connected = False

    def publish(self, payload):
        if self.connected:
            self.event.emit(json.dumps(payload))

    @Slot(str)
    def send(self, raw):
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return
        if not isinstance(data, dict):
            return
        kind = data.get('type')
        island = self.island
        if kind == 'hello':
            self.connected = True
            self.publish({'type': 'auth_ok'})
            self.publish({'type': 'desktop_state', 'state': island.status.text()})
            self.publish({'type': 'desktop_microphone', 'text': 'on' if island.microphone_active else 'off'})
            if island.mail_code:
                self.publish({'type': 'desktop_reply', 'text': island.caption.text()})
                self.publish({'type': 'desktop_mail_review', 'text': island.mail_code})
            if island.request_id:
                self.publish({'type': 'permission_request', 'request_id': island.request_id, 'message': island.caption.text()})
        elif kind == 'command' and not island.busy:
            text = data.get('text')
            if isinstance(text, str) and text.strip() and len(text) <= 16000:
                if data.get('mode') == 'chat':
                    from brain.companion import conversation_text
                    if conversation_text(text) is None:
                        text = 'Chat: ' + text
                island.text_requested.emit(text.strip())
        elif kind == 'listen' and not island.busy:
            if data.get('mode') == 'chat':
                self.conversation_requested.emit()
            else:
                island.start_requested.emit()
        elif kind == 'abort':
            island.stop_requested.emit()
        elif kind == 'send_reviewed_draft' and data.get('code') == island.mail_code:
            island.submit_reviewed_draft()
        elif kind == 'permission_response':
            if data.get('request_id') == island.request_id and isinstance(data.get('approved'), bool) and island.allow.isEnabled():
                island.decide(data['approved'])
        elif kind == 'settings':
            island.settings_requested.emit()
        elif kind in {'get_desktop_settings', 'save_desktop_settings'}:
            self.settings_request.emit(raw)
        elif kind == 'shortcut_capture':
            self.capture_changed.emit(data.get('active') is True)
        elif kind in {'app_access', 'set_app_access'}:
            try:
                if kind == 'set_app_access':
                    app_access.set_choice(data.get('feature'), data.get('enabled'))
                    if data.get('feature') == 'local_ai' and data.get('enabled'):
                        from brain.ollama_runtime import start_local_runtime
                        start_local_runtime()
                choices = app_access.choices()
                from awareness.accounts import token_path
                items = []
                for key, group, label, description in app_access.FEATURES:
                    provider = {'gmail_read': 'gmail', 'gmail_send': 'gmail', 'outlook': 'outlook'}.get(key)
                    account = ''
                    if provider:
                        command = f"python main.py --connect {provider}" + (" --gmail-compose" if key == "gmail_send" else "")
                        account = "Account saved." if token_path(provider).exists() else "Connect using " + command
                        if key == "gmail_send" and token_path(provider).exists():
                            from awareness.accounts import load_token, GMAIL_COMPOSE_SCOPE
                            try:
                                scopes = json.loads(load_token(provider)).get("scopes") or []
                                if GMAIL_COMPOSE_SCOPE not in scopes:
                                    account = "Sending requires " + command
                            except Exception:
                                # Includes unreadable Windows DPAPI tokens and older token formats.
                                account = "Reconnect using " + command
                    items.append({'key': key, 'group': group, 'label': label, 'description': description,
                                  'enabled': choices.get(key, False),
                                  'account': account})
                self.publish({'type': 'app_access', 'items': items})
            except (OSError, ValueError, TypeError):
                self.publish({'type': 'access_error', 'message': 'Could not load or save App access settings.'})
        elif kind == 'quit':
            self.quit_requested.emit()
        elif kind == 'motion':
            island.reduced_motion = bool(data.get('reduced'))
        elif kind == 'get_telemetry':
            if not app_access.allowed("system"):
                self.publish({'type': 'telemetry', 'cpu': None, 'ram': None, 'battery': None})
                return
            battery = psutil.sensors_battery()
            self.publish({'type': 'telemetry', 'cpu': psutil.cpu_percent(),
                          'ram': psutil.virtual_memory().percent,
                          'battery': battery.percent if battery else None})


class DashboardWindow(QWebEngineView):
    """Explicitly opened dashboard; never controlled by island hover."""
    def __init__(self, island):
        super().__init__()
        self.island = island
        self.setWindowTitle("ZENO — Dashboard")
        self.resize(1200, 820)
        self.setMinimumSize(600, 480)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.bridge = DashboardBridge(island)
        self.bridge.setParent(self)
        self.profile = QWebEngineProfile(self)
        self.interceptor = LocalAssetsOnly(self.profile)
        self.profile.setUrlRequestInterceptor(self.interceptor)
        self.dashboard_page = DashboardPage(self.profile, self)
        self.setPage(self.dashboard_page)
        self.dashboard_page.setBackgroundColor(QColor('#1a1a1a'))
        self.dashboard_page.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        self.dashboard_page.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        self.channel = QWebChannel(self.dashboard_page)
        self.channel.registerObject('zeno', self.bridge)
        self.dashboard_page.setWebChannel(self.channel)
        self.dashboard_page.setHtml(dashboard_html(), QUrl.fromLocalFile(str(ROOT / 'server/templates/index.html')))
        self.pending_preferences = False
        self.loadFinished.connect(self._loaded)
        self.escape = QShortcut(QKeySequence('Esc'), self)
        self.escape.activated.connect(island.stop_requested.emit)

    def _loaded(self, okay):
        if okay and self.pending_preferences:
            self.show_preferences()

    def show_preferences(self):
        self.pending_preferences = True
        self.dashboard_page.runJavaScript("if(typeof view === 'function') view('preferences');")

    def handle_event(self, kind, value):
        if kind == 'state':
            self.bridge.publish({'type': 'desktop_state', 'state': value})
        elif kind in {'transcript', 'reply', 'detail', 'draft', 'mail_review', 'service_error', 'microphone', 'level'}:
            self.bridge.publish({'type': 'desktop_' + kind, 'text': value})

    def set_approval(self, request_id, prompt):
        if request_id:
            self.bridge.publish({'type': 'permission_request', 'request_id': request_id,
                                 'message': prompt, 'risk_level': 'Review'})
        else:
            self.bridge.publish({'type': 'desktop_clear_approval'})

    def closeEvent(self, event):
        self.bridge.capture_changed.emit(False)
        self.hide()
        event.ignore()
