"""
Tests for Step 3.5 (Windows details) and Step 3.6 (Clipboard restore).
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from executor.system_ops import SystemOps


def test_disk_usage_uses_home_anchor():
    """Disk usage must use Path.home().anchor, not hardcoded 'C:\\'."""
    ops = SystemOps()
    expected_anchor = Path.home().anchor  # e.g., "C:\\" on most Windows

    with patch("executor.system_ops.psutil") as mock_psutil:
        mock_disk = MagicMock()
        mock_disk.free = 50 * (1024**3)
        mock_disk.total = 500 * (1024**3)
        mock_disk.percent = 90.0
        mock_psutil.disk_usage.return_value = mock_disk

        result = ops.system_info("disk")
        # psutil.disk_usage should be called with the home anchor
        mock_psutil.disk_usage.assert_called_once_with(expected_anchor)
        assert result.success is True
        assert expected_anchor.rstrip("\\") in result.message


def test_volume_set_tries_pycaw_first():
    """Volume control should try pycaw before falling back to key presses."""
    ops = SystemOps()

    # Mock pycaw path
    mock_volume = MagicMock()
    mock_volume.GetMasterVolumeLevelScalar.return_value = 0.5
    mock_devices = MagicMock()
    mock_devices.Activate.return_value = MagicMock()

    with patch("executor.system_ops._get_pycaw_volume", return_value=mock_volume) as mock_get:
        result = ops.volume_set(75)
        mock_get.assert_called_once()
        mock_volume.SetMasterVolumeLevelScalar.assert_called_once_with(0.75, None)
        assert result.success is True


def test_volume_set_falls_back_to_keys_without_pycaw():
    """If pycaw is not installed, volume should fall back to key-press approach."""
    ops = SystemOps()

    with patch("executor.system_ops._get_pycaw_volume", side_effect=ImportError("no pycaw")):
        with patch("executor.system_ops.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0)
            result = ops.volume_set(50)
            assert result.success is True
            assert "approximately" in result.message.lower()


def test_type_text_restores_clipboard():
    """type_text must restore original clipboard after pasting."""
    ops = SystemOps()

    with patch("executor.system_ops.pyperclip") as mock_clip, \
         patch("executor.system_ops.pyautogui") as mock_gui:
        mock_clip.paste.return_value = "original_content"

        result = ops.type_text("hello world")
        assert result.success is True

        # The last call to pyperclip.copy should restore original content
        calls = mock_clip.copy.call_args_list
        assert len(calls) >= 2
        # First call sets new text, last call restores old text
        assert calls[-1].args[0] == "original_content"


def test_type_text_restores_clipboard_on_error():
    """type_text must restore clipboard even if paste operation fails."""
    ops = SystemOps()

    with patch("executor.system_ops.pyperclip") as mock_clip, \
         patch("executor.system_ops.pyautogui") as mock_gui:
        mock_clip.paste.return_value = "precious_data"
        mock_gui.hotkey.side_effect = RuntimeError("paste failed")

        result = ops.type_text("hello")
        # Should still try to restore clipboard
        restore_calls = [c for c in mock_clip.copy.call_args_list if c.args[0] == "precious_data"]
        assert len(restore_calls) >= 1
