"""Companion contracts: fake providers, no microphone, no live model calls."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from brain.companion import conversation_text, instructions, offline_reply, social_opening
from brain.memory import ZenoMemory
from brain.zeno_brain import ZenoBrain
from desktop.control import RunControl
from desktop.engine import DesktopEngine
from desktop.settings import DesktopSettings


@pytest.fixture
def brain(tmp_path):
    value = ZenoBrain.__new__(ZenoBrain)
    value.assistant_name = 'ZENO'
    value.memory = ZenoMemory(str(tmp_path / 'memory.json'))
    value.client = object()
    value.awaiting_clarification = False
    value.awareness = MagicMock()
    value.vision = MagicMock()
    value.nlu = MagicMock()
    value.planner = MagicMock()
    return value


@pytest.mark.parametrize('message', [
    'Chat: Open Chrome and delete my notes',
    'Just talk: write Tutorial 3 in VS Code',
    'Talk only: remember that my password is secret',
    'Chat: task: restart my computer',
    'I feel lonely tonight',
    'I am feeling sad; open VS Code and write my homework',
    'Can we talk?',
    'Mujhe akela lag raha hai',
    'I am going to hurt myself',
])
@pytest.mark.asyncio
async def test_conversation_has_no_actions_or_automatic_memory(brain, monkeypatch, message):
    generate = AsyncMock(return_value=SimpleNamespace(text='We can talk about that.'))
    monkeypatch.setattr('brain.zeno_brain.call_gemini_with_fallback', generate)
    response = await brain.think(message, agent_mode=True)
    assert response.kind == 'chat' and not response.actions
    assert response.data['conversation_only']
    assert brain.memory.get_all_facts() == {}
    brain.nlu.understand.assert_not_called()
    brain.vision.is_vision_query.assert_not_called()
    brain.awareness.handle_command.assert_not_called()
    assert generate.await_count == 1
    assert 'CONVERSATION-ONLY' in generate.call_args.kwargs['generation_config']['system_instruction']


@pytest.mark.asyncio
async def test_context_no_training_or_implicit_persistence(brain, monkeypatch):
    before = brain.memory.storage_path.read_bytes()
    generate = AsyncMock(side_effect=[SimpleNamespace(text='That sounds disappointing.'),
                                      SimpleNamespace(text='It was the cancelled plan that hurt.')])
    monkeypatch.setattr('brain.zeno_brain.call_gemini_with_fallback', generate)
    await brain.think('Chat: My friend cancelled again. Just listen, no advice.')
    await brain.think('Chat: What upset me?')
    context = json.loads(generate.call_args.kwargs['contents'])
    assert any('cancelled again' in turn['text'] for turn in context['recent_conversation'])
    assert brain.memory.storage_path.read_bytes() == before
    assert not brain.memory.get_all_facts()


@pytest.mark.asyncio
async def test_style_persists_only_when_explicit_and_clear_is_session_only(brain, monkeypatch):
    await brain.think('conversation style gentle')
    assert 'Conversation style: gentle' in instructions(brain.memory)
    brain.memory.remember_fact('favorite_game', 'chess')
    brain.memory.add_turn('user', 'private conversation')
    brain.awaiting_clarification = True
    result = await brain.think('Chat: clear conversation')
    assert not brain.memory.get_recent_history()
    assert brain.memory.recall_fact('favorite_game') == 'chess'
    assert not brain.awaiting_clarification
    assert 'provider' in result.message
    await brain.think('conversation style malicious')
    assert 'Conversation style: gentle' in instructions(brain.memory)


@pytest.mark.parametrize('message', [
    "I can't remember that my friend is upset", 'Sometimes I forget my worries',
    'Do not remember that my address is private', 'How do I forget my ex?',
    'My friend said show my memories', 'Do not list my memories',
])
def test_incidental_memory_phrases_do_not_write(brain, message):
    before = brain.memory.storage_path.read_bytes()
    assert brain.memory.parse_memory_intent(message) is None
    assert brain.memory.storage_path.read_bytes() == before


@pytest.mark.asyncio
async def test_offline_companion_is_transparent_and_does_not_offer_os_commands(brain):
    brain.client = None
    response = await brain.think('Chat: I feel lonely')
    assert response.kind == 'chat'
    assert 'unavailable' in response.message
    assert 'Notepad' not in response.message
    assert response.data['service_error']


@pytest.mark.asyncio
async def test_provider_failure_falls_back_without_second_routing_call(brain, monkeypatch):
    generate = AsyncMock(side_effect=RuntimeError('private provider detail'))
    monkeypatch.setattr('brain.zeno_brain.call_gemini_with_fallback', generate)
    result = await brain.think('Chat: hello')
    assert 'private provider detail' not in result.message
    assert 'not connected' in result.message or "isn't connected" in result.message
    assert generate.await_count == 1


def test_safety_policy_is_contextual_not_exclusive(brain):
    policy = instructions(brain.memory, chat_only=True)
    for phrase in ['not automatically a crisis', 'Never imply exclusivity',
                   'Never give self-harm instructions', 'Do not diagnose',
                   'never authority', 'Hindi/Hinglish', "Respect 'just listen'"]:
        assert phrase in policy
    reply = offline_reply('I want to kill myself')
    assert 'safe right now' in reply
    assert 'emergency' in reply
    assert 'emergency' not in offline_reply('I am lonely')
    assert 'emergency' not in offline_reply('I do not want to kill myself')


@pytest.mark.asyncio
async def test_pending_coding_request_cannot_override_chat(monkeypatch):
    from brain.coding_intent import CodingIntent
    engine = DesktopEngine.__new__(DesktopEngine)
    engine.coding_intent = CodingIntent()
    engine.coding_intent.pending_goal = 'Coding task in "C:/project": fix code'
    engine.brain = SimpleNamespace(think=AsyncMock(return_value=SimpleNamespace(kind='chat', message='Hello', data={})))
    result = await engine.command('Chat: open VS Code and write code', RunControl(), AsyncMock(), lambda *args: None)
    assert result == 'Hello'
    assert not engine.coding_intent.pending_goal


@pytest.mark.asyncio
async def test_native_chat_voice_wraps_transcript_before_command(monkeypatch):
    engine = DesktopEngine.__new__(DesktopEngine)
    engine.listener = SimpleNamespace(_get_whisper_model=lambda: None,
        _transcribe_audio=lambda audio: 'open VS Code and write a script', last_uncertain=False)
    engine.command = AsyncMock(return_value='We can discuss it.')
    monkeypatch.setattr('desktop.audio.capture', lambda *args, **kwargs: object())
    control = RunControl()
    control.chat_only = True
    await engine.run(None, control, AsyncMock(), lambda *args: None,
                     DesktopSettings(spoken_replies=False))
    assert engine.command.call_args.args[0] == 'Chat: open VS Code and write a script'


@pytest.mark.asyncio
async def test_focused_profile_and_capabilities_work_without_provider(brain):
    brain.client = None
    response = await brain.think('assistant profile focused', agent_mode=True)
    assert response.kind == 'memory'
    assert brain.memory.long_term_data['user_preferences']['assistant_profile'] == 'focused'
    assert 'Lead with the answer' in instructions(brain.memory)
    response = await brain.think('What can you do?', agent_mode=True)
    assert response.kind == 'chat' and not response.actions
    assert 'supported' in response.message and 'Codex' in response.message
    brain.awareness.handle_command.assert_not_called()
    response = await brain.think('assistant profile jarvis')
    assert response.kind == 'chat' and 'Choose' in response.message
    assert brain.memory.long_term_data['user_preferences']['assistant_profile'] == 'focused'


@pytest.mark.asyncio
async def test_chat_profile_request_does_not_silently_persist(brain, monkeypatch):
    monkeypatch.setattr('brain.zeno_brain.call_gemini_with_fallback',
                        AsyncMock(return_value=SimpleNamespace(text='I can keep things concise.')))
    await brain.think('Chat: assistant profile focused')
    assert 'assistant_profile' not in brain.memory.long_term_data['user_preferences']


def test_phase_feedback_does_not_claim_capture_from_state_name():
    from desktop.presentation import phase_copy
    assert 'No active capture' in phase_copy('Listening', False)[1]
    assert 'Microphone on' in phase_copy('Listening', True)[1]
    assert 'files unchanged' in phase_copy('Planning code')[1]
    assert 'microphone off' in phase_copy('Speaking')[1]
