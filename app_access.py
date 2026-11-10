"""Local user's feature choices. Only the native dashboard can change them."""
import json
import os
import tempfile
from pathlib import Path

from config import config


# id, group, label, operations controlled by the switch
FEATURES = (
    ("gmail_read", "Accounts", "Gmail inbox", "Search and read mail, including background inbox updates."),
    ("gmail_send", "Accounts", "Gmail drafts and sending", "Write Gmail drafts and send with a reviewed draft code."),
    ("outlook", "Accounts", "Microsoft Outlook", "Collect read-only inbox updates from a connected account."),
    ("notifications", "Accounts", "Windows notifications", "Read available app notifications, including messaging apps."),
    ("microphone", "Desktop", "Microphone", "Capture audio for local voice commands."),
    ("screen", "Desktop", "Screen reading and capture", "Inspect your screen, take screenshots and read window controls."),
    ("files", "Desktop", "Files and folders", "Manage files in the folders permitted by ZENO."),
    ("input", "Desktop", "Keyboard and mouse", "Type, paste, press shortcuts and click controls."),
    ("browser", "Desktop", "Web browser", "Open websites and run web searches."),
    ("media", "Desktop", "Media and volume", "Show current playback in the island and control the active player and Windows audio."),
    ("system", "Computer tools", "System information", "Read battery, CPU, memory and running applications."),
    ("power", "Computer tools", "Power controls", "Request lock, sleep, restart or shutdown."),
    ("terminal", "Computer tools", "Terminal diagnostics", "Run supported diagnostic commands."),
    ("local_ai", "AI services", "Local Ollama", "Use installed models for reasoning and screen interpretation."),
    ("cloud_ai", "AI services", "Google Gemini", "Use cloud reasoning when enabled in ZENO configuration."),
    ("online_voice", "AI services", "Online speech services", "Use configured Google speech recognition or Microsoft Edge speech playback."),
    ("coding", "Computer tools", "Coding workspace", "Allow approved project context and code edits through the coding agent."),
    ("monitor", "Computer tools", "Project and process monitoring", "Watch configured Git folders, processes and system health."),
    ("other_apps", "Applications", "Other installed applications", "Launch or close other supported executable names."),
)
APPLICATIONS = {
    "notepad": ("Notepad", ("notepad",)), "chrome": ("Google Chrome", ("chrome", "google chrome")),
    "edge": ("Microsoft Edge", ("msedge", "edge", "microsoft edge")), "firefox": ("Firefox", ("firefox",)),
    "code": ("Visual Studio Code", ("code", "vscode", "code.cmd")), "spotify": ("Spotify", ("spotify",)),
    "office": ("Word and Excel", ("word", "winword", "excel")), "explorer": ("File Explorer", ("explorer", "file explorer")),
    "utilities": ("Windows utilities", ("calculator", "calc", "paint", "mspaint", "settings", "ms-settings:", "systemsettings", "task manager", "taskmgr")),
    "shell_apps": ("Terminal applications", ("terminal", "wt", "powershell", "cmd")),
}
FEATURES += tuple((key, "Applications", title, "Allow ZENO to launch or close this application.")
                  for key, (title, _) in APPLICATIONS.items())
LABELS = {key: title for key, _, title, _ in FEATURES}
ACTION_FEATURES = {
    "system_info": "system", "list_apps": "system", "screenshot": "screen", "ui_inspect": "screen",
    "volume_set": "media", "volume_mute": "media", "media_control": "media", "run_command": "terminal",
    "keyboard_shortcut": "input", "type_text": "input", "mouse_click": "input", "shutdown": "power",
    "open_url": "browser", "web_search": "browser", "folder_create": "files",
    **{f"file_{op}": "files" for op in ("create", "read", "search", "move", "copy", "delete")},
}


def action_feature(action):
    if action.action_type in {"open_app", "close_app"}:
        params = action.parameters or {}
        name = params.get("app_name") if action.action_type == "open_app" else params.get("process_name")
        name = name.strip().lower().removesuffix(".exe") if isinstance(name, str) else ""
        return next((key for key, (_, aliases) in APPLICATIONS.items() if name in aliases), "other_apps")
    return ACTION_FEATURES.get(action.action_type)


def choices():
    try:
        data = json.loads((config.DATA_DIR / "app-access.json").read_text(encoding="utf-8"))
        if not isinstance(data, dict) or any(type(v) is not bool for v in data.values()):
            raise ValueError("Invalid App access settings.")
        return data
    except FileNotFoundError:
        return {}


def allowed(key):
    try:
        return choices().get(key, False)
    except (OSError, ValueError):
        return False


def denial(key):
    return f"{LABELS[key]} is off. Enable it in the desktop dashboard under App access."


def set_choice(key, enabled):
    if key not in LABELS or type(enabled) is not bool:
        raise ValueError("Unknown access setting.")
    data = choices()
    data[key] = enabled
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=config.DATA_DIR, delete=False, mode="w", encoding="utf-8") as out:
        staged = Path(out.name)
        try:
            json.dump(data, out)
        except BaseException:
            out.close()
            staged.unlink(missing_ok=True)
            raise
    try:
        os.replace(staged, config.DATA_DIR / "app-access.json")
    finally:
        staged.unlink(missing_ok=True)
