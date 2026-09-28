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
