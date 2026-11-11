"""A short-lived browser grant owned by the interactive Windows user."""
import ctypes
import hmac
import secrets
import time
import threading
from ctypes import wintypes
from contextlib import contextmanager


def desktop_unlocked():
    try:
        user = ctypes.windll.user32
        user.OpenInputDesktop.restype = wintypes.HANDLE
        handle = user.OpenInputDesktop(0, False, 1)  # DESKTOP_READOBJECTS
        if not handle:
            return False
        handle = wintypes.HANDLE(handle)
        try:
            name = ctypes.create_unicode_buffer(256)
            needed = wintypes.DWORD()
            return bool(user.GetUserObjectInformationW(handle, 2, name, ctypes.sizeof(name),
                                                       ctypes.byref(needed)) and name.value.lower() == "default")
        finally:
            user.CloseDesktop(handle)
    except (AttributeError, OSError):
        return False


_prompt_lock = threading.Lock()


def owner_approves(message):
    if not _prompt_lock.acquire(blocking=False):
        return False
    try:
        return _show_prompt(message)
    finally:
        _prompt_lock.release()


def _show_prompt(message):
    if not desktop_unlocked() or "\0" in message:
        return False
    title = "ZENO remote access"
    response = wintypes.DWORD()
    ok = ctypes.windll.wtsapi32.WTSSendMessageW(
        None, -1, title, len(title.encode("utf-16-le")), message, len(message.encode("utf-16-le")),
        0x104, 30, ctypes.byref(response), True,  # Yes/No, default No
    )
    return bool(ok and response.value == 6 and desktop_unlocked())


class RemoteGrant:
    def __init__(self, scope, origins):
        self.scope = scope
        self.origins = frozenset(origins)
        self.id = secrets.token_hex(16)
        self.code = secrets.token_hex(6)
        self.attempts_left = 5
        self.started = self.last_activity = time.monotonic()

    def revoke(self):
        self.id = ""
        self.code = ""

    def active(self):
        now = time.monotonic()
        if now - self.started >= 900 or now - self.last_activity >= 300 or not desktop_unlocked():
            self.revoke()
        return bool(self.id)

    def consume(self, code):
        if not self.active() or time.monotonic() - self.started >= 300 or not self.code:
            return False
        if self.attempts_left <= 0:
            return False
        self.attempts_left -= 1
        if not hmac.compare_digest(self.code.encode(), code.strip().lower().encode()):
            return False
        self.code = ""
        return True


@contextmanager
def session_notifications(grant):
    """Subscribe before accepting requests so a brief lock also ends the grant."""
    import win32api
    import win32gui
    import win32ts

    def on_session_change(hwnd, message, event, session_id):
        if event in {2, 4, 6, 7}:  # console/remote disconnect, logoff, lock
            grant.revoke()
        return 0

    window = win32gui.WNDCLASS()
    window.lpszClassName = "ZenoRemoteSession" + grant.id
    window.hInstance = win32api.GetModuleHandle(None)
    window.lpfnWndProc = {0x02B1: on_session_change}  # WM_WTSSESSION_CHANGE
    atom = win32gui.RegisterClass(window)
    try:
        hwnd = win32gui.CreateWindow(atom, "", 0, 0, 0, 0, 0, 0, 0, window.hInstance, None)
        try:
            win32ts.WTSRegisterSessionNotification(hwnd, win32ts.NOTIFY_FOR_THIS_SESSION)
            try:
                yield win32gui.PumpWaitingMessages
            finally:
                win32ts.WTSUnRegisterSessionNotification(hwnd)
        finally:
            win32gui.DestroyWindow(hwnd)
    finally:
        win32gui.UnregisterClass(window.lpszClassName, window.hInstance)
