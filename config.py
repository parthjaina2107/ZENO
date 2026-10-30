"""
Central Configuration for Voice Agent
Loads settings from .env file, sets defaults, and validates required parameters.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Base Directory
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file if it exists
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)
# Preserve the key saved during the previous desktop experiment as a fallback.
# Project .env and explicit environment values retain precedence.
if os.getenv("LOCALAPPDATA"):
    load_dotenv(Path(os.environ["LOCALAPPDATA"]) / "ZENO" / ".env")


# Known insecure default secret values
KNOWN_DEFAULT_ACCESS_TOKENS = {
    "voiceagent-secret-passphrase",
    "change_me_to_a_secure_passphrase",
}
KNOWN_DEFAULT_JWT_SECRETS = {
    "voiceagent-jwt-super-secret-key",
    "change_me_to_a_random_secret_key",
}


def ensure_secrets(env_path: Optional[Path] = None) -> tuple[str, str]:
    """
    Ensure ACCESS_TOKEN and JWT_SECRET_KEY are set and non-default.
    Generates cryptographically random 32-byte urlsafe tokens and saves to .env if needed.
    Returns (access_token, jwt_secret_key).
    """
    import secrets
    target_env = Path(env_path) if env_path else BASE_DIR / ".env"

    env_values = {}
    if target_env.exists():
        try:
            for line in target_env.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    env_values[k.strip()] = v.strip()
        except Exception:
            pass

    current_access = env_values.get("ACCESS_TOKEN") or (os.getenv("ACCESS_TOKEN", "").strip() if not env_path else "")
    current_jwt = env_values.get("JWT_SECRET_KEY") or (os.getenv("JWT_SECRET_KEY", "").strip() if not env_path else "")

    needs_access = not current_access or current_access in KNOWN_DEFAULT_ACCESS_TOKENS
    needs_jwt = not current_jwt or current_jwt in KNOWN_DEFAULT_JWT_SECRETS

    new_access = secrets.token_urlsafe(32) if needs_access else current_access
    new_jwt = secrets.token_urlsafe(32) if needs_jwt else current_jwt

    if needs_access or needs_jwt or not target_env.exists():
        existing_lines = []
        if target_env.exists():
            try:
                existing_lines = target_env.read_text(encoding="utf-8").splitlines()
            except Exception:
                existing_lines = []

        updated_lines = []
        found_access = False
        found_jwt = False

        for line in existing_lines:
            if line.startswith("ACCESS_TOKEN="):
                updated_lines.append(f"ACCESS_TOKEN={new_access}")
                found_access = True
            elif line.startswith("JWT_SECRET_KEY="):
                updated_lines.append(f"JWT_SECRET_KEY={new_jwt}")
                found_jwt = True
            else:
                updated_lines.append(line)

        if not found_access:
            updated_lines.append(f"ACCESS_TOKEN={new_access}")
        if not found_jwt:
            updated_lines.append(f"JWT_SECRET_KEY={new_jwt}")

        target_env.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")

    os.environ["ACCESS_TOKEN"] = new_access
    os.environ["JWT_SECRET_KEY"] = new_jwt
    Config.ACCESS_TOKEN = new_access
    Config.JWT_SECRET_KEY = new_jwt
    if "config" in globals():
        config.ACCESS_TOKEN = new_access
        config.JWT_SECRET_KEY = new_jwt

    return new_access, new_jwt


class Config:
    BASE_DIR: Path = BASE_DIR

    # Assistant Persona
    ASSISTANT_NAME: str = os.getenv("ASSISTANT_NAME", "ZENO").strip()
    MEMORY_FILE: str = os.getenv("MEMORY_FILE", str(BASE_DIR / "zeno_memory.json")).strip()

    # API & Auth Credentials
    GEMINI_API_KEY: str = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
    CODING_CODEX_PATH: str = os.getenv("CODING_CODEX_PATH", "").strip()
    CODING_VSCODE_PATH: str = os.getenv("CODING_VSCODE_PATH", "").strip()
    CODING_MODEL: str = os.getenv("CODING_MODEL", "").strip()
    CODING_TIMEOUT_SECONDS: int = max(30, min(3600, int(os.getenv("CODING_TIMEOUT_SECONDS", "900"))))
    GEMINI_FALLBACK_MODELS: list = [
        "gemini-3.6-flash",
        "gemini-3.1-flash-lite",
    ]

    NGROK_AUTH_TOKEN: str = os.getenv("NGROK_AUTH_TOKEN", "").strip()
    ACCESS_TOKEN: str = os.getenv("ACCESS_TOKEN", "").strip()
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "").strip()
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

    # Voice / Audio Settings
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base").strip()
    STT_BACKEND: str = os.getenv("STT_BACKEND", "faster-whisper").strip().lower()
    STT_LANGUAGE: str = os.getenv("STT_LANGUAGE", "").strip()  # Empty: detect English/Hindi/etc.
    STT_ALLOW_ONLINE_FALLBACK: bool = os.getenv("STT_ALLOW_ONLINE_FALLBACK", "true").lower() == "true"
    WAKE_WORD_ENABLED: bool = os.getenv("WAKE_WORD_ENABLED", "false").lower() == "true"
    VOICE_FOLLOWUP_SECONDS: int = max(5, min(120, int(os.getenv("VOICE_FOLLOWUP_SECONDS", "30"))))
    VOICE_BARGE_IN: bool = os.getenv("VOICE_BARGE_IN", "false").lower() == "true"
    LISTEN_TIMEOUT: int = int(os.getenv("LISTEN_TIMEOUT", "5"))
    PHRASE_TIMEOUT: int = int(os.getenv("PHRASE_TIMEOUT", "10"))
    CONFIRMATION_TIMEOUT: int = int(os.getenv("CONFIRMATION_TIMEOUT", "8"))
    REMOTE_CONFIRMATION_TIMEOUT: int = int(os.getenv("REMOTE_CONFIRMATION_TIMEOUT", "60"))
    TTS_BACKEND: str = os.getenv("TTS_BACKEND", "edge").strip().lower()
    TTS_VOICE: str = os.getenv("TTS_VOICE", "en-IN-NeerjaNeural").strip()
    TTS_RATE: str = os.getenv("TTS_RATE", "-12%").strip()
    TTS_VOLUME: str = os.getenv("TTS_VOLUME", "-15%").strip()
    TTS_PITCH: str = os.getenv("TTS_PITCH", "-2Hz").strip()
    TTS_LOCAL_VOICE: str = os.getenv("TTS_LOCAL_VOICE", "Zira").strip()

    # Bounds apply to the whole task, including model-driven continuations.
    AGENT_MAX_STEPS: int = max(1, min(30, int(os.getenv("AGENT_MAX_STEPS", "12"))))
    AGENT_MAX_ROUNDS: int = max(1, min(10, int(os.getenv("AGENT_MAX_ROUNDS", "4"))))
    AGENT_TIMEOUT: int = max(10, int(os.getenv("AGENT_TIMEOUT", "180")))
    AGENT_AUTO_ACTIONS: set = {
        "system_info", "list_apps", "open_app", "open_url", "web_search",
        "volume_set", "media_control", "wait",
    }

    # Auto-Approve Policy (safe read-only actions skip confirmation)
    # Local awareness state is separate from the repository and its Git history.
    DATA_DIR: Path = Path(os.getenv("ZENO_DATA_DIR", str(Path(os.getenv("LOCALAPPDATA", str(Path.home() / '.local' / 'share'))) / "ZENO")))
    AWARENESS_ENABLED: bool = os.getenv("AWARENESS_ENABLED", "true").lower() == "true"
    AWARENESS_POLL_SECONDS: int = max(15, int(os.getenv("AWARENESS_POLL_SECONDS", "60")))
    BRIEFING_INTERVAL_SECONDS: int = max(60, int(os.getenv("BRIEFING_INTERVAL_SECONDS", "900")))
    QUIET_HOURS: str = os.getenv("QUIET_HOURS", "")
    WATCH_PROJECTS: list = [p.strip() for p in os.getenv("WATCH_PROJECTS", str(BASE_DIR)).split(";") if p.strip()]
    OUTLOOK_CLIENT_ID: str = os.getenv("OUTLOOK_CLIENT_ID", "").strip()

    # Only deletion and powering off/restarting require confirmation.
    CONFIRMATION_ACTIONS: set = {"file_delete"}
    CONFIRMATION_POWER_MODES: set = {"shutdown", "restart"}

    @classmethod
    def requires_confirmation(cls, action_type: str, parameters: dict) -> bool:
        return action_type in cls.CONFIRMATION_ACTIONS or (
            action_type == "shutdown"
            and str(parameters.get("mode", "lock")).strip().lower() in cls.CONFIRMATION_POWER_MODES
        )

    # Legacy read-only allowlist; the planner applies the confirmation policy above.
    AUTO_APPROVE_ACTIONS: set = {
        "system_info",      # Battery, CPU, RAM, disk, IP, time — read-only
        "screenshot",       # Captures screen — no system modification
        "list_apps",        # Lists running apps — read-only
    }

    # Server Settings
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0").strip()
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8765"))

    # Logging
    LOG_FILE: str = os.getenv("LOG_FILE", str(BASE_DIR / "voiceagent.log"))

    # Canonical Action Risk Mapping
    ACTION_RISK: dict = {
        "system_info": "low",
        "screenshot": "low",
        "list_apps": "low",
        "ui_inspect": "low",
        "open_app": "low",
        "close_app": "medium",
        "open_url": "low",
        "web_search": "low",
        "volume_set": "low",
        "type_text": "medium",
        "keyboard_shortcut": "medium",
        "mouse_click": "medium",
        "file_create": "medium",
        "file_move": "medium",
        "file_copy": "medium",
        "file_search": "low",
        "file_read": "low",
        "run_command": "high",
        "file_delete": "high",
        "shutdown": "high",
        "media_control": "low",
        "wait": "low",
    }

    # Risk Levels and Action Policies
    RISK_LEVELS: dict = {
        "low": "single_confirm",       # Info queries, screenshot, opening apps
        "medium": "detailed_confirm",   # File ops, typing text, running safe commands
        "high": "double_confirm",      # Deleting files, shutdown, terminal commands
    }

    # Security: File Operations Restrictions
    # By default, file ops are constrained within user directories
    USER_HOME = Path.home()
    ALLOWED_DIRS = [
        str(USER_HOME / "Documents"),
        str(USER_HOME / "Desktop"),
        str(USER_HOME / "Downloads"),
        str(BASE_DIR),  # Allow working inside project dir
    ]
    for _drive_key in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        if os.getenv(_drive_key):
            for _folder in ("Desktop", "Documents"):
                _candidate = Path(os.environ[_drive_key]) / _folder
                if _candidate.is_dir() and str(_candidate) not in ALLOWED_DIRS:
                    ALLOWED_DIRS.append(str(_candidate))

    BLOCKED_PATHS = [
        "C:\\Windows",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "C:\\ProgramData",
        "$Recycle.Bin",
        "System Volume Information",
    ]

    # Safe terminal commands allowlist (first token)
    ALLOWED_COMMANDS: set = {
        "dir",
        "ipconfig",
        "whoami",
        "ping",
        "hostname",
        "netstat",
        "systeminfo",
        "tasklist",
        "route",
        "tracert",
        "nslookup",
        "arp",
        "getmac",
        "curl",
        "echo",
    }

    # Security: Disallowed Shell Commands
    BLOCKED_COMMANDS = [
        "format",
        "del /s /q c:\\",
        "rmdir /s /q c:\\",
        "rm -rf",
        "reg delete",
        "diskpart",
        "bcdedit",
        "cipher /w",
        "sfc",
        "dism",
        "netsh advfirewall set allprofiles state off",
    ]

    @classmethod
    def validate(cls, require_gemini: bool = False, require_ngrok: bool = False) -> list[str]:
        """
        Validates the configuration and returns a list of warning messages.
        If require_gemini is True and key is missing, raises ValueError.
        """
        warnings = []

        if not cls.GEMINI_API_KEY:
            msg = (
                "⚠️ GEMINI_API_KEY is not set. Gemini NLU will fall back to local keyword parsing. "
                "Get a free API key at: https://aistudio.google.com/"
            )
            if require_gemini:
                raise ValueError(msg)
            warnings.append(msg)

        if not cls.NGROK_AUTH_TOKEN:
            msg = (
                "ℹ️ NGROK_AUTH_TOKEN is not set. Remote access tunnel will be disabled. "
                "Local Wi-Fi access will still work. Get token at: https://ngrok.com/"
            )
            if require_ngrok:
                raise ValueError(msg)
            warnings.append(msg)

        if cls.ACCESS_TOKEN in ("change_me_to_a_secure_passphrase", "voiceagent-secret-passphrase", ""):
            warnings.append(
                "⚠️ Default or empty ACCESS_TOKEN is in use. Set a secure passphrase in .env for mobile access."
            )

        return warnings


config = Config()
