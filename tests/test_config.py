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
    assert len(config.GEMINI_FALLBACK_MODELS) >= 2
    assert "gemini-2.5-flash" in config.GEMINI_FALLBACK_MODELS


def test_auto_approve_actions():
    assert hasattr(config, "AUTO_APPROVE_ACTIONS")
    assert "system_info" in config.AUTO_APPROVE_ACTIONS
    assert "screenshot" in config.AUTO_APPROVE_ACTIONS
    assert "list_apps" in config.AUTO_APPROVE_ACTIONS
