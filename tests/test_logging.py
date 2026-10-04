"""
Tests for Step 4.2 (RotatingFileHandler for voiceagent.log).
"""

import logging
from logging.handlers import RotatingFileHandler
from main import setup_logging
from config import config


def test_rotating_file_handler_configured(tmp_path):
    log_file = tmp_path / "test_voiceagent.log"
    handlers = setup_logging(log_file=str(log_file))

    rotating_handlers = [h for h in handlers if isinstance(h, RotatingFileHandler)]
    assert len(rotating_handlers) == 1
    rfh = rotating_handlers[0]
    assert rfh.maxBytes > 0
    assert rfh.backupCount > 0
    assert rfh.encoding.lower() == "utf-8"
