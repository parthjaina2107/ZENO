"""Exercise intent routing, grounded context and speech at the application boundary."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import json

import pytest

from brain.zeno_brain import ZenoBrain
from brain.memory import ZenoMemory
from brain.interaction import is_direct_command, outcome_reply
from brain.planner import ActionResult
from main import VoiceAgentApp


@pytest.fixture
def brain(tmp_path):
    value = ZenoBrain(api_key='')
    value.memory = ZenoMemory(str(tmp_path / 'memory.json'))
    value.client = None
    return value


@pytest.mark.parametrize('utterance', [
    'Why does my laptop restart randomly?',
    'Do not restart my computer',
    'Explain what happens when I open Notepad',
    'Open Spotify and set volume to 30',
    'Write a poem about the moon in Notepad',
    'Type that',
    'Open Notepad, create a file, then read it back',
])
def test_complex_requests_do_not_get_keyword_shortcuts(utterance):
    assert not is_direct_command(utterance)


@pytest.mark.asyncio
async def test_reasoning_routes_goal_and_clarification_with_context(brain, monkeypatch):
    brain.client = object()
    generate = AsyncMock(side_effect=[
        SimpleNamespace(text=json.dumps({'kind': 'clarify', 'message': 'What should the note say?'})),
        SimpleNamespace(text=json.dumps({'kind': 'task', 'message': 'Open Notepad and type Meeting at five.'})),
    ])
    monkeypatch.setattr('brain.interaction.call_gemini_with_fallback', generate)
    brain.nlu.understand = AsyncMock(side_effect=AssertionError('Must reason first'))
    first = await brain.think('Write a note in Notepad')
    second = await brain.think('Meeting at five.')
    assert first.kind == 'chat'
    assert second.kind == 'task'
    prompt = generate.call_args.kwargs['contents']
    assert 'What should the note say?' in prompt and 'Write a note in Notepad' in prompt


@pytest.mark.asyncio
async def test_reasoning_failure_does_not_execute_keyword_match(brain, monkeypatch):
    brain.client = object()
    monkeypatch.setattr('brain.interaction.call_gemini_with_fallback', AsyncMock(return_value=None))
    response = await brain.think('Why does my laptop restart randomly?')
    assert response.kind == 'chat'
    assert not response.actions


@pytest.mark.asyncio
async def test_local_compound_request_speaks_only_one_outcome(brain):
    app = object.__new__(VoiceAgentApp)
    app.brain = brain
    app.speaker = MagicMock()
    app.permissions = MagicMock()
    app.planner = MagicMock()
    app.planner.execute_action.side_effect = [
        ActionResult(True, 'Launched notepad successfully'),
        ActionResult(True, 'Typed and verified 10 characters in Notepad.', output={'verified': True}),
    ]
    await app.process_user_command('Open Notepad and type Hello ZENO')
    app.speaker.speak.assert_called_once_with('The text is in Notepad.')
    assert app.planner.execute_action.call_count == 2
    context = brain.memory.get_recent_history()
    assert any(t['role'] == 'tool' and 'Typed and verified' in t['text'] for t in context)
    assert not any('Planning action' in t['text'] for t in context)


@pytest.mark.asyncio
async def test_unverified_result_never_says_done(brain):
    reply = await outcome_reply(brain, 'type hello', [
        {'action': 'type_text', 'success': True, 'verified': False, 'message': 'sent'}])
    assert "couldn't confirm" in reply


@pytest.mark.asyncio
async def test_failed_task_does_not_read_traceback(brain):
    reply = await outcome_reply(brain, 'do something', [], 'failed', 'Traceback C:/private/file.py JSON 500')
    assert 'Traceback' not in reply and 'private' not in reply


@pytest.mark.asyncio
async def test_battery_answer_keeps_requested_information(brain):
    reply = await outcome_reply(brain, 'check battery', [
        {'action': 'system_info', 'success': True, 'message': 'Battery is at 70%, charging.'}])
    assert '70%' in reply
