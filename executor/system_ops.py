"""
System Operations for Voice Agent:
App management, process control, system power states, volume, screenshots,
mouse/keyboard input, and safe command execution.
"""

import os
import subprocess
import socket
import logging
import base64
import io
import datetime
from typing import Optional, List, Dict, Any
from brain.planner import ActionResult
from config import config

logger = logging.getLogger("VoiceAgent.SystemOps")

# Critical Windows processes that must NEVER be killed
PROTECTED_PROCESSES = {
    "csrss.exe", "svchost.exe", "lsass.exe", "winlogon.exe", "smss.exe",
    "services.exe", "explorer.exe", "dwm.exe", "system", "idle",
    "registry", "fontdrvhost.exe", "sihost.exe"
}

# Common application name to executable mappings on Windows
APP_EXECUTABLE_MAP = {
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "firefox": "firefox.exe",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "terminal": "wt.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "vscode": "code.cmd",
    "code": "code.cmd",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "settings": "ms-settings:",
    "spotify": "spotify.exe",
    "paint": "mspaint.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
}


class SystemOps:
    def __init__(self):
        self._init_pyautogui()

    def _init_pyautogui(self):
        try:
            import pyautogui
            pyautogui.FAILSAFE = True  # Move mouse to corner to abort
            pyautogui.PAUSE = 0.05
        except Exception as e:
            logger.warning(f"Could not configure pyautogui: {e}")

    # ==================== APPLICATION MANAGEMENT ====================

    def open_app(self, app_name: str) -> ActionResult:
        """Launch an application by friendly name or executable name."""
        name_clean = app_name.strip().lower()
        target = APP_EXECUTABLE_MAP.get(name_clean, app_name.strip())

        try:
            if target.startswith("ms-settings:"):
                os.startfile(target)
                return ActionResult(success=True, message=f"Opened Windows Settings.")

            # Attempt 1: startfile
            try:
                os.startfile(target)
                return ActionResult(success=True, message=f"Launched '{app_name}' successfully.")
            except Exception:
                pass

            # Attempt 2: subprocess.Popen
            try:
                subprocess.Popen(target, shell=True)
                return ActionResult(success=True, message=f"Started '{app_name}' via shell.")
            except Exception:
                pass

            # Attempt 3: Windows 'start' command
            subprocess.Popen(f'start "" "{target}"', shell=True)
            return ActionResult(success=True, message=f"Invoked start for '{app_name}'.")

        except Exception as e:
            logger.error(f"Failed to open app '{app_name}': {e}")
            return ActionResult(success=False, message=f"Failed to open '{app_name}'.", error=str(e))

    def close_app(self, process_name: str) -> ActionResult:
        """Close an application process gracefully by name."""
        import psutil
        clean_name = process_name.strip().lower()
        if not clean_name.endswith(".exe") and not "." in clean_name:
            target_name = f"{clean_name}.exe"
        else:
            target_name = clean_name

        if target_name in PROTECTED_PROCESSES:
            return ActionResult(
                success=False,
                message=f"Access denied: '{target_name}' is a protected Windows system process.",
                error="PROTECTED_PROCESS"
            )

        terminated_count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                pname = proc.info['name'].lower()
                if pname == target_name or clean_name in pname:
                    proc.terminate()
                    terminated_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        if terminated_count > 0:
            return ActionResult(success=True, message=f"Closed {terminated_count} instance(s) of '{process_name}'.")
        else:
            return ActionResult(
                success=False,
                message=f"No running process matching '{process_name}' found.",
                error="PROCESS_NOT_FOUND"
            )

    def list_running_apps(self, limit: int = 25) -> ActionResult:
        """Return a list of top active user processes."""
        import psutil
        apps = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
            try:
                name = proc.info['name']
                if name.lower() not in PROTECTED_PROCESSES and not name.startswith("System"):
                    apps.append(name)
            except Exception:
                continue

        unique_apps = sorted(list(set(apps)))[:limit]
        return ActionResult(
            success=True,
            message=f"Found {len(unique_apps)} active user applications.",
            output=unique_apps
        )

    # ==================== SYSTEM CONTROL & POWER ====================

    def shutdown(self, mode: str = "lock") -> ActionResult:
        """Execute shutdown, restart, sleep, or lock."""
        mode_clean = mode.strip().lower()

        try:
            if mode_clean == "shutdown":
                subprocess.run("shutdown /s /t 5", shell=True)
                return ActionResult(success=True, message="Computer is shutting down in 5 seconds.")
            elif mode_clean == "restart":
                subprocess.run("shutdown /r /t 5", shell=True)
                return ActionResult(success=True, message="Computer is restarting in 5 seconds.")
            elif mode_clean == "sleep":
                subprocess.run("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
                return ActionResult(success=True, message="Putting computer to sleep.")
            elif mode_clean == "lock":
                subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True)
                return ActionResult(success=True, message="Workstation locked.")
            else:
                return ActionResult(
                    success=False,
                    message=f"Unsupported power mode: '{mode}'. Use shutdown, restart, sleep, or lock.",
                    error="INVALID_MODE"
                )
        except Exception as e:
            return ActionResult(success=False, message=f"Power command failed: {e}", error=str(e))

    def volume_set(self, level: int) -> ActionResult:
        """Set Windows system volume (0-100)."""
        level = max(0, min(100, int(level)))
        try:
            # PowerShell audio helper script using SoundVolumeView or SAPI/nircmd or SendKeys
            # On Windows without 3rd party tools, we can step volume up or down or use pycaw if installed
            # Alternatively use Windows Volume Virtual Keys or powershell WScript.Shell
            import pyautogui
            if level == 0:
                pyautogui.press("volumemute")
                return ActionResult(success=True, message="Volume muted.")
            
            # Approximate volume adjustment via media keys or powershell
            ps_script = f"""
            $obj = New-Object -ComObject WScript.Shell
            1..50 | ForEach-Object {{ $obj.SendKeys([char]174) }}
            1..{int(level / 2)} | ForEach-Object {{ $obj.SendKeys([char]175) }}
            """
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], timeout=5)
            return ActionResult(success=True, message=f"System volume adjusted to approximately {level}%.")
        except Exception as e:
            return ActionResult(success=False, message=f"Failed to adjust volume: {e}", error=str(e))

    def screenshot(self) -> ActionResult:
        """Capture screenshot, save to file, and return base64 encoded thumbnail."""
        try:
            import pyautogui
            from PIL import Image

            shot = pyautogui.screenshot()
            
            # Ensure screenshots directory
            save_dir = config.BASE_DIR / "screenshots"
            save_dir.mkdir(exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = save_dir / f"screenshot_{timestamp}.png"
            shot.save(str(file_path))

            # Generate base64 thumbnail for web preview
            thumb = shot.copy()
            thumb.thumbnail((1280, 720))
            buffer = io.BytesIO()
            thumb.save(buffer, format="JPEG", quality=80)
            b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

            return ActionResult(
                success=True,
                message=f"Screenshot captured and saved to: {file_path.name}",
                output={
                    "file_path": str(file_path),
                    "base64": f"data:image/jpeg;base64,{b64_str}"
                }
            )
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return ActionResult(success=False, message=f"Failed to capture screenshot: {e}", error=str(e))

    def system_info(self, info_type: str = "battery") -> ActionResult:
        """Query system telemetry: battery, CPU, RAM, disk, IP, time."""
        import psutil
        clean_type = info_type.strip().lower()

        try:
            if clean_type in ("battery", "power"):
                battery = psutil.sensors_battery()
                if not battery:
                    return ActionResult(success=True, message="No battery sensor detected (Desktop PC or plugged in AC).")
                percent = battery.percent
                plugged = "plugged in" if battery.power_plugged else "on battery power"
                mins = int(battery.secsleft / 60) if battery.secsleft > 0 else None
                time_str = f", ~{mins} mins remaining" if mins else ""
                return ActionResult(
                    success=True,
                    message=f"Battery is at {percent}%, {plugged}{time_str}.",
                    output={"percent": percent, "plugged": battery.power_plugged}
                )

            elif clean_type in ("cpu", "processor"):
                cpu = psutil.cpu_percent(interval=0.5)
                cores = psutil.cpu_count(logical=True)
                return ActionResult(
                    success=True,
                    message=f"Current CPU usage is {cpu}% across {cores} cores.",
                    output={"cpu_percent": cpu, "cores": cores}
                )

            elif clean_type in ("ram", "memory"):
                mem = psutil.virtual_memory()
                used_gb = round(mem.used / (1024**3), 2)
                total_gb = round(mem.total / (1024**3), 2)
                return ActionResult(
                    success=True,
                    message=f"RAM usage is {mem.percent}% ({used_gb} GB used of {total_gb} GB).",
                    output={"percent": mem.percent, "used_gb": used_gb, "total_gb": total_gb}
                )

            elif clean_type in ("disk", "storage"):
                disk = psutil.disk_usage('C:\\')
                free_gb = round(disk.free / (1024**3), 1)
                total_gb = round(disk.total / (1024**3), 1)
                return ActionResult(
                    success=True,
                    message=f"C: Drive has {free_gb} GB free out of {total_gb} GB ({disk.percent}% used).",
                    output={"percent": disk.percent, "free_gb": free_gb, "total_gb": total_gb}
                )

            elif clean_type in ("ip", "network"):
                hostname = socket.gethostname()
                ip = socket.gethostbyname(hostname)
                return ActionResult(
                    success=True,
                    message=f"Hostname is '{hostname}', Local IP is {ip}.",
                    output={"hostname": hostname, "ip": ip}
                )

            elif clean_type in ("time", "clock", "date"):
                now = datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
                return ActionResult(
                    success=True,
                    message=f"Current time is {now}.",
                    output={"time_str": now}
                )

            else:
                return ActionResult(
                    success=False,
                    message=f"Unknown info type: '{info_type}'. Available: battery, cpu, ram, disk, ip, time.",
                    error="UNKNOWN_INFO_TYPE"
                )

        except Exception as e:
            return ActionResult(success=False, message=f"Failed to query system info: {e}", error=str(e))

    # ==================== KEYBOARD & MOUSE ====================

    def type_text(self, text: str) -> ActionResult:
        """Type text using clipboard paste for Unicode safety, fallback to typewrite."""
        try:
            import pyperclip
            import pyautogui
            # Using clipboard paste preserves emoji, symbols, newlines accurately
            old_clip = ""
            try:
                old_clip = pyperclip.paste()
            except Exception:
                pass

            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")

            return ActionResult(success=True, message=f"Typed {len(text)} characters.")
        except Exception as e:
            return ActionResult(success=False, message=f"Failed to type text: {e}", error=str(e))

    def keyboard_shortcut(self, keys: List[str]) -> ActionResult:
        """Press keyboard shortcut keys simultaneously (e.g., ['ctrl', 's'])."""
        try:
            import pyautogui
            # Normalize keys to lowercase
            clean_keys = [k.strip().lower() for k in keys]
            pyautogui.hotkey(*clean_keys)
            return ActionResult(success=True, message=f"Pressed hotkey: {' + '.join(clean_keys)}")
        except Exception as e:
            return ActionResult(success=False, message=f"Failed to trigger hotkey: {e}", error=str(e))

    def mouse_click(self, x: int, y: int, button: str = "left") -> ActionResult:
        """Click mouse at specified coordinate."""
        try:
            import pyautogui
            btn = button.lower() if button.lower() in ("left", "right", "middle") else "left"
            pyautogui.click(x=int(x), y=int(y), button=btn)
            return ActionResult(success=True, message=f"Clicked {btn} button at ({x}, {y}).")
        except Exception as e:
            return ActionResult(success=False, message=f"Failed mouse click: {e}", error=str(e))

    # ==================== TERMINAL COMMANDS ====================

    def run_command(self, command: str) -> ActionResult:
        """Execute safe shell command with 30s timeout and output capture."""
        clean_cmd = command.strip()
        lowered = clean_cmd.lower()

        # Security check
        for blocked in config.BLOCKED_COMMANDS:
            if blocked in lowered:
                return ActionResult(
                    success=False,
                    message=f"Command blocked by safety policy: '{blocked}'.",
                    error="BLOCKED_COMMAND"
                )

        try:
            res = subprocess.run(
                clean_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            output = res.stdout if res.returncode == 0 else (res.stderr or res.stdout)
            # Truncate long output
            if len(output) > 2000:
                output = output[:2000] + "\n...[output truncated]"

            success = res.returncode == 0
            msg = f"Command finished with exit code {res.returncode}:\n{output}" if output else f"Command completed (code {res.returncode})."
            return ActionResult(success=success, message=msg, output=output)
        except subprocess.TimeoutExpired:
            return ActionResult(success=False, message="Command timed out after 30 seconds.", error="TIMEOUT")
        except Exception as e:
            return ActionResult(success=False, message=f"Command execution error: {e}", error=str(e))
