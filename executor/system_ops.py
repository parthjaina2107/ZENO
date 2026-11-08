"""
System Operations for Voice Agent:
App management, process control, system power states, volume, screenshots,
mouse/keyboard input, and safe command execution.
"""

from contextlib import contextmanager
import os
import re
import subprocess
import socket
import logging
import base64
import io
import datetime
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from brain.planner import ActionResult
from config import config

try:
    import psutil
except ImportError:
    psutil = None

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import pyperclip
except ImportError:
    pyperclip = None

logger = logging.getLogger("VoiceAgent.SystemOps")

@contextmanager
def _get_pycaw_volume():
    """Use the audio endpoint on the calling worker's COM apartment."""
    import comtypes
    from pycaw.pycaw import AudioUtilities

    comtypes.CoInitialize()
    try:
        device = AudioUtilities.GetSpeakers()
        if device is None:
            raise RuntimeError("No default Windows audio endpoint.")
        yield device.EndpointVolume
    finally:
        comtypes.CoUninitialize()


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


def installed_application(name: str):
    """Resolve a launch target without searching the current working directory."""
    system = Path(os.environ.get("SystemRoot", "C:/Windows"))
    directories = [system / "System32", system]
    directories.extend(Path(p.strip('"')) for p in os.get_exec_path() if p)
    for directory in directories:
        if directory.is_absolute() and directory.resolve() != Path.cwd().resolve():
            candidate = directory / name
            if candidate.is_file():
                return candidate
    if os.name == "nt":
        import winreg
        app = "Code.exe" if name == "code.cmd" else name
        key = r"Software\Microsoft\Windows\CurrentVersion\App Paths" + "\\" + app
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, key) as entry:
                    candidate = Path(os.path.expandvars(winreg.QueryValueEx(entry, "")[0].strip('"')))
                if candidate.is_absolute() and candidate.is_file() and candidate.suffix.lower() == ".exe":
                    return candidate
            except OSError:
                continue
    return None


class SystemOps:
    def __init__(self):
        self._last_opened_app = None
        self._init_pyautogui()

    def media_control(self, command: str) -> ActionResult:
        """Send a media key to the active media session; do not claim playback verified."""
        keys = {"play_pause": "playpause", "next": "nexttrack", "previous": "prevtrack", "stop": "stop"}
        if command not in keys or pyautogui is None:
            return ActionResult(False, "Media control is unavailable or invalid.", error="MEDIA_UNAVAILABLE")
        try:
            pyautogui.press(keys[command])
            return ActionResult(True, f"Sent media command: {command}. Playback depends on the active player.")
        except Exception as exc:
            return ActionResult(False, f"Media control failed: {exc}", error="MEDIA_FAILED")

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
        self._last_opened_app = None
        known = {value.lower(): value for value in APP_EXECUTABLE_MAP.values()}
        target = APP_EXECUTABLE_MAP.get(name_clean) or known.get(name_clean)
        if target is None:
            if not re.fullmatch(r"[\w -]+(?:\.exe)?", name_clean):
                return ActionResult(False, "Specify an installed application name.", error="INVALID_APP")
            target = name_clean.removesuffix(".exe") + ".exe"

        try:
            if target == "ms-settings:":
                os.startfile(target)
            else:
                executable = installed_application(target)
                if executable is None:
                    return ActionResult(False, "Application executable was not found.", error="APP_NOT_FOUND")
                os.startfile(str(executable))
            self._last_opened_app = name_clean
            return ActionResult(True, f"Requested launch of '{app_name}'.")
        except Exception as e:
            logger.error(f"Failed to open app '{app_name}': {e}")
            return ActionResult(success=False, message=f"Failed to open '{app_name}'.", error=str(e))

    def close_app(self, process_name: str) -> ActionResult:
        """Close an application process gracefully by name."""
        import psutil
        clean_name = process_name.strip().lower()
        if not clean_name:
            return ActionResult(False, "Specify an application to close.", error="INVALID_ARGUMENTS")
        target_name = APP_EXECUTABLE_MAP.get(clean_name, clean_name)
        if target_name.endswith(".cmd"):
            target_name = target_name.removesuffix(".cmd") + ".exe"
        if target_name == "ms-settings:":
            target_name = "systemsettings.exe"
        if "." not in target_name:
            target_name += ".exe"

        if clean_name in PROTECTED_PROCESSES or target_name in PROTECTED_PROCESSES:
            return ActionResult(
                success=False,
                message=f"Access denied: '{target_name}' is a protected Windows system process.",
                error="PROTECTED_PROCESS"
            )

        terminated_count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                pname = (proc.info['name'] or '').lower()
                if pname == target_name:
                    proc.terminate()
                    terminated_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        if terminated_count > 0:
            return ActionResult(success=True, message=f"Requested closure of {terminated_count} instance(s) of '{process_name}'.")
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
            if mode_clean in {"shutdown", "restart"}:
                flag = "/s" if mode_clean == "shutdown" else "/r"
                exe = Path(os.environ["SystemRoot"]) / "System32" / "shutdown.exe"
                subprocess.run([str(exe), flag, "/t", "5"], check=True, timeout=10)
                return ActionResult(True, f"Windows accepted the {mode_clean} request for five seconds from now.")
            elif mode_clean in {"lock", "sleep"}:
                import ctypes
                if mode_clean == "lock":
                    ok = ctypes.windll.user32.LockWorkStation()
                else:
                    ok = ctypes.windll.powrprof.SetSuspendState(False, False, False)
                if not ok:
                    return ActionResult(False, f"Windows rejected the {mode_clean} request.", error="POWER_FAILED")
                return ActionResult(True, f"Windows accepted the {mode_clean} request.")
            else:
                return ActionResult(
                    success=False,
                    message=f"Unsupported power mode: '{mode}'. Use shutdown, restart, sleep, or lock.",
                    error="INVALID_MODE"
                )
        except Exception as e:
            return ActionResult(success=False, message=f"Power command failed: {e}", error=str(e))

    def volume_mute(self, muted: bool) -> ActionResult:
        try:
            with _get_pycaw_volume() as endpoint:
                endpoint.SetMute(muted, None)
                if bool(endpoint.GetMute()) != muted:
                    raise RuntimeError("The audio endpoint did not confirm the requested state.")
            return ActionResult(True, "Volume muted." if muted else "Volume unmuted.")
        except Exception as exc:
            return ActionResult(False, "Could not set the system mute state.", error=str(exc))

    def volume_set(self, level: int) -> ActionResult:
        """Set Windows system volume (0-100)."""
        level = max(0, min(100, int(level)))
        try:
            try:
                with _get_pycaw_volume() as volume:
                    volume.SetMasterVolumeLevelScalar(level / 100.0, None)
                return ActionResult(success=True, message=f"System volume set to {level}%.")
            except Exception as pycaw_err:
                logger.debug(f"pycaw not available or failed ({pycaw_err}), falling back to keys")
                # Lower the level first. A mute key would toggle an already muted device.
                ps_script = f"""
                $obj = New-Object -ComObject WScript.Shell
                1..50 | ForEach-Object {{ $obj.SendKeys([char]174) }}
                for ($i = 0; $i -lt {int(level / 2)}; $i++) {{ $obj.SendKeys([char]175) }}
                """
                subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], timeout=5, check=True)
                return ActionResult(success=True, message=f"System volume adjusted to approximately {level}%.")
        except Exception as e:
            return ActionResult(success=False, message=f"Failed to adjust volume: {e}", error=str(e))

    def screenshot(self) -> ActionResult:
        """Capture screenshot, save to file, and return base64 encoded thumbnail."""
        try:
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
                anchor = Path.home().anchor
                disk = psutil.disk_usage(anchor)
                free_gb = round(disk.free / (1024**3), 1)
                total_gb = round(disk.total / (1024**3), 1)
                clean_anchor = anchor.rstrip("\\")
                return ActionResult(
                    success=True,
                    message=f"{clean_anchor} Drive has {free_gb} GB free out of {total_gb} GB ({disk.percent}% used).",
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
        """Type text using clipboard paste for Unicode safety, restoring clipboard in finally."""
        if self._last_opened_app in ("notepad", "notepad.exe"):
            try:
                from .notepad_input import NotepadInput
                output = NotepadInput().paste(text, pyperclip, pyautogui)
                return ActionResult(True, f"Typed and verified {len(text)} characters in Notepad.", output=output)
            except Exception as exc:
                return ActionResult(False, f"Could not verify Notepad typing: {exc}", error="NOTEPAD_INPUT_FAILED")
        old_clip = None
        try:
            try:
                old_clip = pyperclip.paste()
            except Exception:
                old_clip = None

            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.3)

            return ActionResult(success=True, message=f"Paste sent ({len(text)} characters); delivery to this application is unverified.", output={"verified": False})
        except Exception as e:
            return ActionResult(success=False, message=f"Failed to type text: {e}", error=str(e))
        finally:
            if old_clip is not None:
                try:
                    pyperclip.copy(old_clip)
                except Exception:
                    pass

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
        """Execute safe shell command with allowlist, shell=False, 30s timeout and output capture."""
        import shlex
        clean_cmd = command.strip(" \t")
        if not clean_cmd:
            return ActionResult(success=False, message="Empty command provided.", error="EMPTY_COMMAND")

        try:
            tokens = shlex.split(clean_cmd, posix=False)
        except ValueError:
            return ActionResult(False, "Unbalanced command quotes.", error="INVALID_ARGUMENTS")

        if not tokens:
            return ActionResult(success=False, message="Empty command provided.", error="EMPTY_COMMAND")

        if any(c in clean_cmd for c in '\r\n\x00'):
            return ActionResult(False, "Shell expressions are unsupported.", error="BLOCKED_COMMAND")
        args = []
        for part in tokens[1:]:
            if len(part) >= 2 and part[0] == part[-1] and part[0] in {'"', "'"}:
                args.append(part[1:-1])
            elif any(c in part for c in '&|<>^;'):
                return ActionResult(False, "Shell expressions are unsupported.", error="BLOCKED_COMMAND")
            else:
                args.append(part)
        first_token = tokens[0].lower().removesuffix(".exe")

        # Security Layer: Blocked commands blacklist
        lowered = clean_cmd.lower()
        for blocked in config.BLOCKED_COMMANDS:
            if blocked in lowered:
                return ActionResult(
                    success=False,
                    message=f"Command blocked by safety policy: '{blocked}'.",
                    error="BLOCKED_COMMAND"
                )

        # Security Layer: Allowlist of first tokens
        if first_token not in config.ALLOWED_COMMANDS:
            return ActionResult(
                success=False,
                message=f"Command '{first_token}' is not in the allowed list of safe commands.",
                error="COMMAND_NOT_ALLOWED"
            )

        if first_token == "echo":
            output = clean_cmd[len(tokens[0]):].lstrip()
            if len(args) == 1:
                output = args[0]
            return ActionResult(True, output, output=output)
        if first_token == "dir":
            paths = [part for part in args if part.lower() != "/b"]
            if len(paths) > 1:
                return ActionResult(False, "Use dir with one directory.", error="INVALID_ARGUMENTS")
            try:
                folder = Path(paths[0] if paths else ".")
                output = "\n".join(sorted(item.name for item in folder.iterdir()))[:2000]
                return ActionResult(True, output or "Empty directory.", output=output)
            except (ValueError, OSError) as exc:
                return ActionResult(False, "Directory listing failed.", error=str(exc))
        readonly = {"route": [["print"]], "ipconfig": [[], ["/all"]], "arp": [["-a"]]}
        if first_token in readonly and [arg.lower() for arg in args] not in readonly[first_token]:
            return ActionResult(False, "Use a read-only diagnostic invocation.", error="INVALID_ARGUMENTS")
        if first_token == "curl":
            if len(args) != 1 or not args[0].lower().startswith(("http://", "https://")):
                return ActionResult(False, "Use curl with one HTTP or HTTPS URL.", error="INVALID_ARGUMENTS")
            args = ["-q", "--globoff", "--", args[0]]
        if first_token == "nslookup" and (not args or any(a.startswith("-") for a in args)):
            return ActionResult(False, "Use nslookup with a host name.", error="INVALID_ARGUMENTS")
        executable = first_token
        if os.name == "nt":
            executable = str(Path(os.environ["SystemRoot"]) / "System32" / (first_token + ".exe"))
        exec_args = [executable, *args]

        try:
            res = subprocess.run(
                exec_args,
                shell=False,
                capture_output=True,
                text=True,
                timeout=30
            )
            output = res.stdout if res.returncode == 0 else (res.stderr or res.stdout)
            # Truncate long output
            if output and len(output) > 2000:
                output = output[:2000] + "\n...[output truncated]"

            success = res.returncode == 0
            msg = f"Command finished with exit code {res.returncode}:\n{output}" if output else f"Command completed (code {res.returncode})."
            return ActionResult(success=success, message=msg, output=output)
        except subprocess.TimeoutExpired:
            return ActionResult(success=False, message="Command timed out after 30 seconds.", error="TIMEOUT")
        except Exception as e:
            return ActionResult(success=False, message=f"Command execution error: {e}", error=str(e))

