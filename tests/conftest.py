"""
Pytest configuration and common test fixtures.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock

# Gracefully provide mock fallbacks for headless CI environments
for mod_name in ["pyaudio", "win32com", "win32com.client"]:
    if mod_name not in sys.modules:
        try:
            __import__(mod_name)
        except Exception:
            sys.modules[mod_name] = MagicMock()


@pytest.fixture(autouse=True)
def mock_headless_environment_if_ci(monkeypatch):
    """Ensure headless CI runners (e.g. GitHub Actions) don't crash on GUI calls."""
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        try:
            import pyautogui
            from PIL import Image
            monkeypatch.setattr(pyautogui, "size", lambda: (1920, 1080))
            dummy_img = Image.new("RGB", (100, 100), color="blue")
            monkeypatch.setattr(pyautogui, "screenshot", lambda *a, **kw: dummy_img)
        except Exception:
            pass


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
