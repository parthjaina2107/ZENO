"""
Unit tests for config.py
"""

from pathlib import Path
from config import config, Config


def test_config_defaults():
    assert config.SERVER_PORT > 0
    assert "low" in config.RISK_LEVELS
    assert "medium" in config.RISK_LEVELS
    assert "high" in config.RISK_LEVELS


def test_blocked_commands():
    assert "format" in config.BLOCKED_COMMANDS
    assert "rm -rf" in config.BLOCKED_COMMANDS


def test_allowed_dirs():
    assert len(config.ALLOWED_DIRS) > 0
    for d in config.ALLOWED_DIRS:
        assert Path(d).is_absolute()


def test_fallback_models():
    assert hasattr(config, "GEMINI_FALLBACK_MODELS")
    assert len(config.GEMINI_FALLBACK_MODELS) >= 1
    assert "gemini-2.0-flash" in config.GEMINI_FALLBACK_MODELS


def test_auto_approve_actions():
    assert hasattr(config, "AUTO_APPROVE_ACTIONS")
    assert "system_info" in config.AUTO_APPROVE_ACTIONS
    assert "screenshot" in config.AUTO_APPROVE_ACTIONS
    assert "list_apps" in config.AUTO_APPROVE_ACTIONS


def test_ensure_secrets_creates_random_values(tmp_path):
    from config import ensure_secrets
    env_file = tmp_path / ".env"
    access_token, jwt_secret = ensure_secrets(env_path=env_file)
    assert env_file.exists()
    assert len(access_token) >= 32
    assert len(jwt_secret) >= 32
    assert access_token not in ("voiceagent-secret-passphrase", "change_me_to_a_secure_passphrase")
    assert jwt_secret not in ("voiceagent-jwt-super-secret-key", "change_me_to_a_random_secret_key")

    content = env_file.read_text(encoding="utf-8")
    assert f"ACCESS_TOKEN={access_token}" in content
    assert f"JWT_SECRET_KEY={jwt_secret}" in content


def test_token_forged_with_old_default_secret_rejected():
    from jose import jwt
    from server.auth import AuthManager
    am = AuthManager()
    am.secret_key = "new-random-secret-key-123456789012"
    old_default_secret = "voiceagent-jwt-super-secret-key"
    forged = jwt.encode({"sub": "mobile_client", "role": "controller"}, old_default_secret, algorithm="HS256")
    assert am.verify_session_token(forged) is None
