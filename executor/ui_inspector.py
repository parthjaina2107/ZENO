"""Best-effort semantic desktop inspection with a safe, dependency-free fallback."""

import ctypes
from typing import Any, Dict

from brain.planner import ActionResult


class UIInspector:
    def active_window(self) -> ActionResult:
        """Report the focused window and, when available, accessibility controls.

        pywinauto is intentionally optional: ZENO remains usable without it while
        installations that add it receive richer control labels and roles.
        """
        title = "Desktop"
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buffer = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value or title
        except Exception:
            hwnd = 0

        output: Dict[str, Any] = {"window_title": title, "window_handle": int(hwnd or 0), "controls": []}
        try:
            from pywinauto import Desktop  # optional extra
            window = Desktop(backend="uia").window(handle=hwnd)
            controls = []
            for control in window.descendants()[:80]:
                info = control.element_info
                if info.name or info.control_type:
                    controls.append({"name": info.name or "", "role": info.control_type or ""})
            output["controls"] = controls
            output["accessibility_available"] = True
        except Exception:
            output["accessibility_available"] = False

        suffix = f" I found {len(output['controls'])} accessible controls." if output["accessibility_available"] else " Install pywinauto for named control discovery."
        return ActionResult(True, f"Focused window: {title}.{suffix}", output=output)
