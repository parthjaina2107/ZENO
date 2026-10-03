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
    GEMINI_FALLBACK_MODELS: list = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ]
    NGROK_AUTH_TOKEN: str = os.getenv("NGROK_AUTH_TOKEN", "").strip()
    ACCESS_TOKEN: str = os.getenv("ACCESS_TOKEN", "").strip()
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "").strip()
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

    # Voice / Audio Settings
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base").strip()
    LISTEN_TIMEOUT: int = int(os.getenv("LISTEN_TIMEOUT", "5"))
    PHRASE_TIMEOUT: int = int(os.getenv("PHRASE_TIMEOUT", "10"))
    CONFIRMATION_TIMEOUT: int = int(os.getenv("CONFIRMATION_TIMEOUT", "8"))
    REMOTE_CONFIRMATION_TIMEOUT: int = int(os.getenv("REMOTE_CONFIRMATION_TIMEOUT", "60"))

    # Auto-Approve Policy (safe read-only actions skip confirmation)
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
