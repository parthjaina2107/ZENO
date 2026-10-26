"""Target Notepad's editable document and verify pasted text through accessibility."""
import time


class NotepadInput:
    def find_editor(self, timeout=8):
        from pywinauto import Desktop
        import psutil
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            candidates = []
            for window in Desktop(backend="uia").windows():
                try:
                    if psutil.Process(window.element_info.process_id).name().lower() == "notepad.exe" and window.is_visible():
                        candidates.append(window)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            active = [window for window in candidates if window.is_active()]
            windows = active if len(active) == 1 else candidates
            if len(windows) == 1:
                window = windows[0]
                editors = [c for c in window.descendants() if c.element_info.control_type in ("Document", "Edit") and c.is_visible() and c.is_enabled()]
                documents = [c for c in editors if c.element_info.control_type == "Document"]
                editors = documents or editors
                if len(editors) == 1:
                    return window, editors[0]
            elif len(windows) > 1:
                raise RuntimeError("Several Notepad windows are open. Focus the intended window before typing.")
            time.sleep(0.2)
        raise RuntimeError("Notepad's editable document did not become ready.")

    @staticmethod
    def read(editor):
        try:
            return editor.iface_value.CurrentValue
        except Exception:
            return editor.iface_text.DocumentRange.GetText(-1)

    @staticmethod
    def normalized(text):
        return text.replace("\r\n", "\n").rstrip("\r")

    def paste(self, text, clipboard, keyboard):
        window, editor = self.find_editor()
        before = self.normalized(self.read(editor))
        window.set_focus()
        editor.set_focus()
        # Append explicitly instead of replacing an existing selection or document.
        keyboard.hotkey("ctrl", "end")
        old_clipboard = clipboard.paste()
        try:
            clipboard.copy(text)
            keyboard.hotkey("ctrl", "v")
            deadline = time.monotonic() + 4
            expected = self.normalized(before + text)
            while time.monotonic() < deadline:
                after = self.normalized(self.read(editor))
                if after == expected:
                    return {"verified": True, "application": "notepad", "window_handle": window.handle, "characters": len(text)}
                time.sleep(0.1)
            raise RuntimeError("Notepad did not contain the expected text after paste. Clipboard was restored; no retry was sent.")
        finally:
            clipboard.copy(old_clipboard)
