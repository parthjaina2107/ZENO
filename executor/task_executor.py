"""
Task Executor
Central dispatching engine routing PlannedAction objects to specialized subsystems
(SystemOps, BrowserOps, FileOps).
"""

import logging
from typing import Dict, Any
from brain.planner import PlannedAction, ActionResult
from .system_ops import SystemOps
from .browser_ops import BrowserOps
from .file_ops import FileOps

logger = logging.getLogger("VoiceAgent.TaskExecutor")


class TaskExecutor:
    def __init__(self):
        self.system = SystemOps()
        self.browser = BrowserOps()
        self.file = FileOps()

    def execute(self, action: PlannedAction) -> ActionResult:
        """Execute a planned action and return an ActionResult."""
        act_type = action.action_type
        params = action.parameters or {}
        logger.info(f"Executing action '{act_type}' with parameters: {params}")

        try:
            # === APPLICATION MANAGEMENT ===
            if act_type == "open_app":
                app_name = params.get("app_name", "")
                return self.system.open_app(app_name)

            elif act_type == "close_app":
                proc_name = params.get("process_name", "")
                return self.system.close_app(proc_name)

            elif act_type == "list_apps":
                return self.system.list_running_apps()

            # === BROWSER OPERATIONS ===
            elif act_type == "open_url":
                url = params.get("url", "")
                return self.browser.open_url(url)

            elif act_type == "web_search":
                query = params.get("query", "")
                return self.browser.web_search(query)

            # === KEYBOARD & MOUSE ===
            elif act_type == "type_text":
                text = params.get("text", "")
                return self.system.type_text(text)

            elif act_type == "keyboard_shortcut":
                keys = params.get("keys", [])
                return self.system.keyboard_shortcut(keys)

            elif act_type == "mouse_click":
                x = params.get("x", 0)
                y = params.get("y", 0)
                btn = params.get("button", "left")
                return self.system.mouse_click(x, y, btn)

            # === TERMINAL ===
            elif act_type == "run_command":
                cmd = params.get("command", "")
                return self.system.run_command(cmd)

            # === FILE OPERATIONS ===
            elif act_type == "file_create":
                path = params.get("path", "")
                content = params.get("content", "")
                return self.file.file_create(path, content)

            elif act_type == "file_delete":
                path = params.get("path", "")
                return self.file.file_delete(path)

            elif act_type == "file_move":
                src = params.get("source", "")
                dst = params.get("destination", "")
                return self.file.file_move(src, dst)

            elif act_type == "file_copy":
                src = params.get("source", "")
                dst = params.get("destination", "")
                return self.file.file_copy(src, dst)

            elif act_type == "file_search":
                directory = params.get("directory", "Desktop")
                pattern = params.get("pattern", "*")
                return self.file.file_search(directory, pattern)

            elif act_type == "file_read":
                path = params.get("path", "")
                return self.file.file_read(path)

            # === SYSTEM & POWER ===
            elif act_type == "screenshot":
                return self.system.screenshot()

            elif act_type == "volume_set":
                lvl = params.get("level", 50)
                return self.system.volume_set(lvl)

            elif act_type == "system_info":
                info_type = params.get("type", "battery")
                return self.system.system_info(info_type)

            elif act_type == "shutdown":
                mode = params.get("mode", "lock")
                return self.system.shutdown(mode)

            elif act_type in ("unhandled", "unknown"):
                return ActionResult(
                    success=False,
                    message=action.description or "I didn't understand that command.",
                    error="UNRECOGNIZED_COMMAND"
                )

            else:
                return ActionResult(
                    success=False,
                    message=f"No execution handler registered for action type: '{act_type}'",
                    error="UNREGISTERED_ACTION"
                )

        except Exception as e:
            logger.exception(f"Unexpected error executing action '{act_type}': {e}")
            return ActionResult(success=False, message=f"Execution failed: {e}", error=str(e))
