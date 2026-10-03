"""
Pytest configuration and common test fixtures.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock


class FakeSpeaker:
    def __init__(self):
        self.spoken = []
        self._running = True

    def speak(self, text: str):
        if text:
            self.spoken.append(text)

    def speak_sync(self, text: str):
        if text:
            self.spoken.append(text)

    def speak_async(self, text: str):
        self.speak(text)

    def stop(self):
        self._running = False


class FakeListener:
    def __init__(self, canned_confirmation=None, canned_speech=""):
        self.canned_confirmation = canned_confirmation
        self.canned_speech = canned_speech
        self._mic_available = True

    def is_mic_available(self) -> bool:
        return self._mic_available

    def listen_once(self, timeout: int = 5, phrase_time_limit: int = 10):
        return self.canned_speech

    def listen_for_confirmation(self, timeout: int = 8):
        return self.canned_confirmation

    def stop(self):
        pass


@pytest.fixture
def temp_audit_log(tmp_path: Path):
    """Fixture providing a temporary audit log path."""
    log_path = tmp_path / "test_audit_log.jsonl"
    return str(log_path)


@pytest.fixture
def temp_memory_file(tmp_path: Path):
    """Fixture providing a temporary memory JSON file."""
    mem_path = tmp_path / "test_zeno_memory.json"
    return str(mem_path)


@pytest.fixture
def fake_speaker():
    """Fixture providing a fake speaker."""
    return FakeSpeaker()


@pytest.fixture
def fake_listener():
    """Fixture providing a fake listener."""
    return FakeListener()
