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
    from config import config
    monkeypatch.setattr(config, 'STT_BACKEND', 'whisper')
    monkeypatch.setattr(VoiceListener, '_init_speech_recognition', lambda self: None)

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


def test_local_speech_load_failure_is_throttled_and_no_online_fallback(monkeypatch):
    from unittest.mock import MagicMock
    from voice.listener import VoiceListener
    from config import config
    monkeypatch.setattr(VoiceListener, '_init_speech_recognition', lambda self: None)
    monkeypatch.setattr(config, 'STT_BACKEND', 'faster-whisper')
    monkeypatch.setattr(config, 'STT_ALLOW_ONLINE_FALLBACK', False)
    loader = MagicMock(side_effect=RuntimeError('not cached'))
    monkeypatch.setattr('voice.local_stt.load_model', loader)
    listener = VoiceListener()
    listener._recognizer = MagicMock()
    assert listener._transcribe_audio(MagicMock()) is None
    assert listener._transcribe_audio(MagicMock()) is None
    loader.assert_called_once()
    listener._recognizer.recognize_google.assert_not_called()


def test_faster_whisper_preserves_unicode_and_uses_vad(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from voice.local_stt import transcribe
    model = MagicMock()
    model.transcribe.return_value = (iter([SimpleNamespace(text=' Hello'), SimpleNamespace(text=' नमस्ते ')]), None)
    audio = MagicMock()
    audio.get_wav_data.return_value = b'fake wav'
    assert transcribe(model, audio) == 'Hello नमस्ते'
    assert model.transcribe.call_args.kwargs['vad_filter'] is True
    assert model.transcribe.call_args.kwargs['condition_on_previous_text'] is False


def test_local_silence_does_not_trigger_google(monkeypatch):
    from unittest.mock import MagicMock
    from voice.listener import VoiceListener
    from config import config
    monkeypatch.setattr(VoiceListener, '_init_speech_recognition', lambda self: None)
    monkeypatch.setattr(config, 'STT_BACKEND', 'faster-whisper')
    monkeypatch.setattr(config, 'STT_ALLOW_ONLINE_FALLBACK', True)
    monkeypatch.setattr('voice.local_stt.transcribe', lambda *a: None)
    listener = VoiceListener()
    listener._whisper_model = MagicMock()
    listener._recognizer = MagicMock()
    assert listener._transcribe_audio(MagicMock()) is None
    listener._recognizer.recognize_google.assert_not_called()

