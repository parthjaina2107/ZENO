"""
Central Configuration for Voice Agent
Loads settings from .env file, sets defaults, and validates required parameters.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file if it exists
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)


class Config:
    BASE_DIR: Path = BASE_DIR

    # API & Auth Credentials
    GEMINI_API_KEY: str = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
    NGROK_AUTH_TOKEN: str = os.getenv("NGROK_AUTH_TOKEN", "").strip()
    ACCESS_TOKEN: str = os.getenv("ACCESS_TOKEN", "voiceagent-secret-passphrase").strip()
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "voiceagent-jwt-super-secret-key").strip()
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

    # Voice / Audio Settings
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base").strip()
    LISTEN_TIMEOUT: int = int(os.getenv("LISTEN_TIMEOUT", "5"))
    PHRASE_TIMEOUT: int = int(os.getenv("PHRASE_TIMEOUT", "10"))
    CONFIRMATION_TIMEOUT: int = int(os.getenv("CONFIRMATION_TIMEOUT", "15"))
    REMOTE_CONFIRMATION_TIMEOUT: int = int(os.getenv("REMOTE_CONFIRMATION_TIMEOUT", "60"))

    # Server Settings
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0").strip()
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8765"))

    # Logging
    LOG_FILE: str = os.getenv("LOG_FILE", str(BASE_DIR / "voiceagent.log"))

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
