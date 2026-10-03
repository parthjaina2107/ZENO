"""
Unit tests for confirmation parsing in VoiceListener.
"""

import pytest
from voice.listener import parse_confirmation


def test_parse_confirmation_denials():
    assert parse_confirmation("no thanks") is False
    assert parse_confirmation("cancel that") is False
    assert parse_confirmation("no that's wrong") is False
    assert parse_confirmation("stop") is False
    assert parse_confirmation("never") is False


def test_parse_confirmation_approvals():
    assert parse_confirmation("yes") is True
    assert parse_confirmation("go ahead") is True
    assert parse_confirmation("sure") is True
    assert parse_confirmation("approved") is True
    assert parse_confirmation("do it") is True


def test_parse_confirmation_ambiguous_and_neutral():
    assert parse_confirmation("yes no") is None
    assert parse_confirmation("maybe") is None
    assert parse_confirmation("i don't know") is False  # 'don't' is a deny word
    assert parse_confirmation("what do you think") is None


def test_parse_confirmation_removed_ambiguous_words():
    # 'ha', 'right', 'please', 'correct' must not approve
    assert parse_confirmation("right") is None
    assert parse_confirmation("correct") is None
    assert parse_confirmation("please") is None
    assert parse_confirmation("ha") is None


def test_whisper_lazy_load(monkeypatch):
    import sys
    from unittest.mock import MagicMock
    from voice.listener import VoiceListener

    mock_whisper = MagicMock()
    mock_model = MagicMock()
    mock_whisper.load_model.return_value = mock_model
    monkeypatch.setitem(sys.modules, "whisper", mock_whisper)

    listener = VoiceListener()
    assert listener._whisper_model is None
    # Trigger lazy load
    loaded = listener._get_whisper_model()
    assert loaded is mock_model
    mock_whisper.load_model.assert_called_once()

