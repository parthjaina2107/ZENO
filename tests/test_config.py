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
    assert "gemini-3.1-flash-lite" in config.GEMINI_FALLBACK_MODELS


def test_auto_approve_actions():
    assert hasattr(config, "AUTO_APPROVE_ACTIONS")
    assert "system_info" in config.AUTO_APPROVE_ACTIONS
    assert "screenshot" in config.AUTO_APPROVE_ACTIONS
    assert "list_apps" in config.AUTO_APPROVE_ACTIONS


def test_generated_credentials_live_only_in_process(tmp_path, monkeypatch):
    from config import ensure_secrets
    monkeypatch.setattr(config, "ACCESS_TOKEN", "")
    monkeypatch.setattr(config, "JWT_SECRET_KEY", "")
    monkeypatch.setattr(config, "generated_passphrase", False)
    monkeypatch.setattr(config, "BASE_DIR", tmp_path)
    ensure_secrets()
    assert config.generated_passphrase
    assert len(config.ACCESS_TOKEN) >= 32 and len(config.JWT_SECRET_KEY) >= 32
    assert not list(tmp_path.iterdir())


def test_token_forged_with_old_default_secret_rejected():
    import jwt
    from server.auth import AuthManager
    am = AuthManager()
    am.secret_key = "new-random-secret-key-123456789012"
    old_default_secret = "voiceagent-jwt-super-secret-key"
    import pytest
    with pytest.warns(jwt.InsecureKeyLengthWarning):
        forged = jwt.encode({"sub": "mobile_client", "role": "controller"}, old_default_secret, algorithm="HS256")
    assert am.verify_session_token(forged) is None


def test_retention_only_removes_expired_generated_history(tmp_path, monkeypatch):
    import os
    from executor.history import prune_history
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "HISTORY_RETENTION_DAYS", 30)
    shots = tmp_path / "screenshots"
    shots.mkdir()
    old = shots / "screenshot_20260101_100000.png"
    personal = shots / "holiday.png"
    recent = shots / "screenshot_20261111_100000_123456.png"
    for path in (old, personal, recent):
        path.write_bytes(b"test")
    for path in (old, personal):
        os.utime(path, (1000000000, 1000000000))
    prune_history()
    assert not old.exists() and recent.exists() and personal.exists()
