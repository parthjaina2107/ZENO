"""Native registered shortcut, not a keyboard hook or a key logger."""
import ctypes
from ctypes import wintypes
import sys

from PySide6.QtCore import QAbstractNativeEventFilter


def parse_shortcut(text):
    parts = text.upper().replace(" ", "").split("+")
    modifiers = {"CTRL": 2, "ALT": 1, "SHIFT": 4}
    if not parts or not parts[-1]:
        raise ValueError("Choose a shortcut, for example Ctrl+Alt+Z.")
    mods = 0
    for part in parts[:-1]:
        if part not in modifiers or mods & modifiers[part]:
            raise ValueError("Use Ctrl, Alt or Shift with a letter, number or function key.")
        mods |= modifiers[part]
    key = parts[-1]
    if len(key) == 1 and key.isascii() and key.isalnum():
        if not mods & 3:
            raise ValueError("Letters and numbers need Ctrl or Alt so normal typing stays unaffected.")
        vk = ord(key)
    elif key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        if key == "F12":
            raise ValueError("Windows reserves F12. Choose another key.")
        vk = 0x70 + int(key[1:]) - 1
    else:
        raise ValueError("Use a letter, number or F1–F24 (except Windows-reserved F12).")
    if (mods, key) in {(1, "F4"), (2, "W"), (2, "C"), (2, "V"), (2, "X"), (2, "Z")}:
        raise ValueError("That is a common editing or window shortcut. Add Alt or choose another key.")
    return mods | 0x4000, vk  # MOD_NOREPEAT ignores held-key repeats.


class GlobalHotkey(QAbstractNativeEventFilter):
    def __init__(self, application, callback, api=None):
        super().__init__()
        if api is None:
            if sys.platform != "win32":
                raise RuntimeError("Global desktop shortcuts currently require Windows.")
            api = ctypes.WinDLL("user32", use_last_error=True)
            api.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
            api.RegisterHotKey.restype = wintypes.BOOL
            api.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
            api.UnregisterHotKey.restype = wintypes.BOOL
        self.api, self.application, self.callback = api, application, callback
        self.binding = ""
        self.active_id = None
        application.installNativeEventFilter(self)

    def register(self, text):
        mods, key = parse_shortcut(text)
        if text == self.binding:
            return
        next_id = 0x5A01 if self.active_id != 0x5A01 else 0x5A02
        if not self.api.RegisterHotKey(None, next_id, mods, key):
            raise ValueError("This shortcut is unavailable or used by another app. Your previous shortcut is unchanged.")
        old = self.active_id
        self.active_id, self.binding = next_id, text
        if old is not None:
            self.api.UnregisterHotKey(None, old)

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and msg.wParam == self.active_id:
                self.callback()
                return True, 0
        return False, 0

    def close(self):
        if self.active_id is not None:
            self.api.UnregisterHotKey(None, self.active_id)
            self.active_id = None
            self.binding = ""
        self.application.removeNativeEventFilter(self)
