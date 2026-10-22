"""Voice boundaries and cancellation without a microphone, network, or OS actions."""
import queue
import sys
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from voice.conversation import ConversationSession, interrupt_intent
from voice.speaker import VoiceSpeaker


def test_wake_required_and_not_a_substring():
    session = ConversationSession(True, clock=lambda: 100)
    for text in ('open notepad', 'Zenoise open notepad', 'they said hey zeno open notepad'):
        assert session.accept(text).kind == 'ignore'
    turn = session.accept('Hey ZENO, open Notepad')
    assert (turn.kind, turn.text) == ('command', 'open Notepad')


def test_wake_alone_followups_expiry_and_sleep():
    now = [100]
    session = ConversationSession(True, clock=lambda: now[0])
    assert session.accept('Hey ZENO').kind == 'prompt'
    assert session.accept('check its changes').kind == 'command'
    now[0] += 31
    assert session.accept('open spotify').kind == 'ignore'
    session.accept('Zeno')
    assert session.accept('go to sleep').kind == 'sleep'
    assert session.accept('open spotify').kind == 'ignore'


def test_direct_mode_and_explicit_sleep():
    session = ConversationSession(False, clock=lambda: 100)
    assert session.accept('open spotify').text == 'open spotify'
    session.accept('stop listening')
    assert session.accept('open spotify').kind == 'ignore'
    assert session.accept('hey zeno open spotify').kind == 'command'


def test_uncertain_transcript_cannot_execute_without_clear_confirmation():
    session = ConversationSession(clock=lambda: 100)
    assert session.accept('restart computer', uncertain=True).kind == 'prompt'
    assert session.accept('yes', uncertain=True).kind == 'prompt'
    # An uncertain yes never confirms the original command.
    assert session.accept('no').kind == 'prompt'
    session.accept('open Notepad', uncertain=True)
    assert session.accept('yes').text == 'open Notepad'


def test_pending_confirmation_expiry_and_replacement():
    now = [100]
    session = ConversationSession(clock=lambda: now[0])
    session.accept('delete file', uncertain=True)
    now[0] += 21
    assert session.accept('yes').kind == 'prompt'
    session.accept('delete file', uncertain=True)
    assert session.accept('check battery').text == 'check battery'


def test_uncertain_yes_does_not_replace_pending_request():
    session = ConversationSession(clock=lambda: 100)
    session.accept('open Notepad', uncertain=True)
    session.accept('yes', uncertain=True)
    assert session.accept('yes').text == 'open Notepad'


def test_punctuated_wake_alone_prompts_instead_of_executing():
    assert ConversationSession(True, clock=lambda: 100).accept('Hey Zeno.').kind == 'prompt'


@pytest.mark.parametrize('text', ['stop', 'Hey Zeno, wait', 'ZENO stop speaking', "that's not what I meant"])
def test_interrupts_are_exact_controls(text):
    assert interrupt_intent(text)


@pytest.mark.parametrize('text', ['type stop in Notepad', 'do not stop', 'wait then delete file', 'stop spotify', 'zenoise stop'])
def test_interrupts_do_not_match_embedded_or_negated_commands(text):
    assert interrupt_intent(text) is None


def bare_speaker():
    value = object.__new__(VoiceSpeaker)
    value._speech_queue = queue.Queue()
    value._generation = 0
    value._queue_lock = threading.Lock()
    return value


def test_interrupt_drains_queue_and_keeps_future_speech_usable():
    speaker = bare_speaker()
    speaker.speak('old reply')
    speaker.interrupt()
    assert not speaker.is_busy
    speaker.speak('new reply')
    assert speaker._speech_queue.get_nowait() == (1, 'new reply')
    speaker._speech_queue.task_done()
    speaker.wait_until_idle()


def test_interrupt_preserves_active_queue_accounting():
    speaker = bare_speaker()
    speaker.speak('active')
    speaker._speech_queue.get_nowait()  # Simulate worker ownership.
    speaker.speak('pending')
    speaker.interrupt()
    assert speaker.is_busy
    speaker._speech_queue.task_done()
    assert not speaker.is_busy


@pytest.mark.asyncio
async def test_barge_in_never_executes_an_ambient_command(monkeypatch):
    from config import config
    from main import VoiceAgentApp
    monkeypatch.setattr(config, 'VOICE_BARGE_IN', True)
    app = object.__new__(VoiceAgentApp)
    app.running = True
    app.speaker = MagicMock()
    app.speaker.is_busy = True
    app.listener = MagicMock(last_uncertain=False)
    app.conversation = ConversationSession()
    app.brain = MagicMock()
    app.process_user_command = AsyncMock()
    app.listener.listen_once.side_effect = ['delete my file', 'hey zeno stop']
    await app.wait_for_reply()
    app.speaker.interrupt.assert_called_once()
    app.process_user_command.assert_not_called()
    assert all(call.args[-1] is True for call in app.listener.listen_once.call_args_list)


def test_decoder_quality_flags_uncertain_text():
    from voice.local_stt import transcribe
    audio = MagicMock()
    audio.get_wav_data.return_value = b'audio'
    model = MagicMock()
    model.transcribe.return_value = (iter([SimpleNamespace(text='restart', avg_logprob=-1.5)]), None)
    quality = {}
    assert transcribe(model, audio, quality) == 'restart'
    assert quality['uncertain'] is True


def test_standby_never_uses_google_fallback(monkeypatch):
    from voice.listener import VoiceListener
    monkeypatch.setattr(VoiceListener, '_init_speech_recognition', lambda self: None)
    listener = VoiceListener()
    listener._recognizer = MagicMock()
    monkeypatch.setattr(listener, '_get_whisper_model', lambda: None)
    assert listener._transcribe_audio(MagicMock(), local_only=True) is None
    listener._recognizer.recognize_google.assert_not_called()


def test_worker_interrupts_neural_playback_and_can_speak_again(monkeypatch):
    from config import config
    monkeypatch.setattr(config, 'TTS_BACKEND', 'edge')
    started, cancelled, finished = threading.Event(), threading.Event(), threading.Event()
    def neural(text, running):
        if text == 'old':
            started.set()
            while running():
                cancelled.wait(0.01)
            cancelled.set()
        else:
            finished.set()
    monkeypatch.setattr('voice.neural.speak_neural', neural)
    speaker = VoiceSpeaker()
    try:
        speaker.speak('old')
        assert started.wait(3)
        speaker.speak('discard me')
        speaker.interrupt()
        assert cancelled.wait(2)
        assert not finished.is_set()
        speaker.speak('new')
        assert finished.wait(2)
        speaker.wait_until_idle()
    finally:
        speaker.stop()


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows SAPI worker')
def test_worker_purges_sapi_on_interruption(monkeypatch):
    import win32com.client
    from config import config
    monkeypatch.setattr(config, 'TTS_BACKEND', 'sapi')
    started, purged = threading.Event(), threading.Event()
    voice = MagicMock()
    voice.GetVoices.return_value = []
    def speak(text, flags):
        if flags == 1:
            started.set()
        elif flags == 3:
            purged.set()
    voice.Speak.side_effect = speak
    voice.WaitUntilDone.side_effect = lambda timeout: purged.wait(0.01)
    monkeypatch.setattr(win32com.client, 'Dispatch', lambda name: voice)
    speaker = VoiceSpeaker()
    try:
        speaker.speak('cancel this reply')
        assert started.wait(3)
        speaker.interrupt()
        assert purged.wait(2)
        speaker.wait_until_idle()
    finally:
        speaker.stop()


def test_uncertain_permission_approval_is_not_accepted(monkeypatch):
    from voice.listener import VoiceListener
    monkeypatch.setattr(VoiceListener, '_init_speech_recognition', lambda self: None)
    listener = VoiceListener()
    def listen(**kwargs):
        listener.last_uncertain = True
        return 'yes'
    monkeypatch.setattr(listener, 'listen_once', listen)
    times = iter([0, 0, 0, 9])
    monkeypatch.setattr('voice.listener.time.time', lambda: next(times))
    assert listener.listen_for_confirmation(timeout=8) is None


@pytest.mark.asyncio
async def test_wake_loop_never_routes_unaddressed_speech(monkeypatch):
    from config import config
    from main import VoiceAgentApp
    monkeypatch.setattr(config, 'VOICE_BARGE_IN', False)
    app = object.__new__(VoiceAgentApp)
    app.running, app.text_mode = True, False
    app.conversation = ConversationSession(True)
    app.speaker = MagicMock()
    app.listener = MagicMock(last_uncertain=False)
    heard = iter(['open spotify', 'hey zeno open Notepad'])
    app.listener.listen_once.side_effect = lambda *args: next(heard)
    async def execute(text):
        assert text == 'open Notepad'
        app.running = False
    app.process_user_command = AsyncMock(side_effect=execute)
    await app.run_local_loop()
    app.process_user_command.assert_awaited_once_with('open Notepad')


@pytest.mark.asyncio
async def test_uncertain_voice_turn_waits_before_execution(monkeypatch):
    from config import config
    from main import VoiceAgentApp
    monkeypatch.setattr(config, 'VOICE_BARGE_IN', False)
    app = object.__new__(VoiceAgentApp)
    app.running, app.text_mode = True, False
    app.conversation = ConversationSession()
    app.speaker = MagicMock()
    app.listener = MagicMock()
    phrases = iter([('open Notepad', True), ('yes', False)])
    def listen(*args):
        text, app.listener.last_uncertain = next(phrases)
        return text
    app.listener.listen_once.side_effect = listen
    async def execute(text):
        app.running = False
    app.process_user_command = AsyncMock(side_effect=execute)
    await app.run_local_loop()
    app.process_user_command.assert_awaited_once_with('open Notepad')
    assert any('I may have heard' in call.args[0] for call in app.speaker.speak.call_args_list)
