from unittest.mock import AsyncMock, MagicMock

import pytest

from brain.folder_intent import folder_request, folder_name
from brain.zeno_brain import ZenoBrain
from brain.memory import ZenoMemory
from brain.interaction import outcome_reply
from config import config
from desktop.control import RunControl
from desktop.engine import DesktopEngine
from executor.file_ops import FileOps
from executor.task_executor import TaskExecutor


@pytest.mark.parametrize('utterance', ['create a folder named Parth on desktop',
    'make a new folder on my desktop called Parth', 'please create folder Parth on the desktop'])
def test_explicit_folder_request(utterance):
    assert folder_request(utterance) == {'location': 'Desktop', 'name': 'Parth'}


@pytest.mark.parametrize('utterance', ['do not create a folder', 'how do I create a folder?',
    'create a folder A on desktop and delete the old files', 'create a folder in C:/Windows'])
def test_not_a_simple_folder_command(utterance):
    assert folder_request(utterance) is None


@pytest.mark.parametrize('name', ['../outside', 'CON', 'NUL.txt', 'a:b', 'folder\\other', '..'])
def test_folder_names_cannot_escape_or_use_windows_devices(name):
    assert folder_name(name) is None


@pytest.fixture
def desktop_engine(tmp_path, monkeypatch):
    desktop = tmp_path / 'OneDrive' / 'Desktop'
    desktop.mkdir(parents=True)
    monkeypatch.setattr('executor.file_ops.user_folder', lambda name: desktop)
    executor = TaskExecutor()
    executor.file = FileOps([str(desktop)])
    brain = ZenoBrain(api_key='', executor=executor)
    brain.memory = ZenoMemory(str(tmp_path / 'memory.json'))
    # The request must work even when the configured local model is unavailable.
    monkeypatch.setattr(config, 'LOCAL_LLM_ENABLED', True)
    cloud = AsyncMock(side_effect=AssertionError('Simple folder requests must not call a model'))
    monkeypatch.setattr('brain.zeno_brain.route_request', cloud)
    engine = DesktopEngine.__new__(DesktopEngine)
    engine.brain, engine.permissions, engine.awareness = brain, MagicMock(), None
    return engine, desktop


@pytest.mark.asyncio
async def test_desktop_folder_request_runs_without_model(desktop_engine):
    engine, desktop = desktop_engine
    reply = await engine.command('create a folder called Parth on desktop', RunControl(), AsyncMock(), MagicMock())
    assert (desktop / 'Parth').is_dir()
    assert 'Created folder "Parth"' in reply
    reply = await engine.command('create a folder called Parth on desktop', RunControl(), AsyncMock(), MagicMock())
    assert 'already exists' in reply


@pytest.mark.asyncio
async def test_missing_folder_name_is_clarified_locally(desktop_engine):
    engine, desktop = desktop_engine
    reply = await engine.command('create a folder on desktop', RunControl(), AsyncMock(), MagicMock())
    assert 'What should I name' in reply and not list(desktop.iterdir())
    reply = await engine.command('call it Parth', RunControl(), AsyncMock(), MagicMock())
    assert (desktop / 'Parth').is_dir()


@pytest.mark.asyncio
async def test_cancel_clears_pending_folder(desktop_engine):
    engine, desktop = desktop_engine
    await engine.brain.think('create a folder on desktop')
    await engine.brain.think('cancel')
    assert engine.brain.pending_folder_location is None
    assert not list(desktop.iterdir())


def test_folder_creation_preserves_existing_files_and_bounds(tmp_path):
    allowed = tmp_path / 'allowed'
    allowed.mkdir()
    target = allowed / 'existing'
    target.write_text('preserve me')
    ops = FileOps([str(allowed)])
    assert not ops.folder_create(str(target)).success
    assert target.read_text() == 'preserve me'
    assert not ops.folder_create(str(allowed / '..' / 'outside')).success
    assert not (tmp_path / 'outside').exists()


@pytest.mark.asyncio
async def test_failure_shows_reason_without_another_model_call(desktop_engine, monkeypatch):
    engine, _ = desktop_engine
    generate = AsyncMock(side_effect=AssertionError('Do not ask failed AI to explain its failure'))
    monkeypatch.setattr('brain.interaction.call_gemini_with_fallback', generate)
    message = await outcome_reply(engine.brain, 'create folder', [], 'failed',
                                  'Access denied: Path is outside permitted directories')
    assert 'permitted' in message and 'Desktop' in message and 'console' not in message
    generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_desktop_runs_literal_diagnostic_and_rejects_chain(desktop_engine):
    engine, _ = desktop_engine
    approve = AsyncMock(return_value=True)
    emit = MagicMock()
    # Exercise the same offline routing, policy, executor and reply used by the island.
    for command, expected in [
        ('run command echo "MiXeD ZENO"', 'MiXeD ZENO'),
        ('run command echo ok & whoami', 'Shell expressions are unsupported'),
    ]:
        emit.reset_mock()
        reply = await engine.command(command, RunControl(), approve, emit)
        assert expected in reply
        assert any(expected in str(call.args) for call in emit.call_args_list)
    approve.assert_not_awaited()


@pytest.mark.asyncio
async def test_desktop_time_and_media_requests_reach_expected_actions(desktop_engine, monkeypatch):
    from brain.planner import ActionResult
    engine, _ = desktop_engine
    media = MagicMock(return_value=ActionResult(True, "Sent pause key"))
    system = engine.brain.planner.executor.system
    monkeypatch.setattr(system, "media_control", media)
    time_reply = await engine.command("what time is it", RunControl(), AsyncMock(), MagicMock())
    assert "Current time" in time_reply
    await engine.command("pause music", RunControl(), AsyncMock(), MagicMock())
    media.assert_called_once_with("pause")


@pytest.mark.asyncio
async def test_new_command_after_folder_prompt_keeps_its_own_intent(desktop_engine):
    brain = desktop_engine[0].brain
    await brain.think("create a folder on desktop")
    assert (await brain.think("pause music")).actions[0].action_type == "media_control"
    result = await brain.think("open Notepad then check battery")
    assert [a.action_type for a in result.actions] == ["open_app", "system_info"]
    assert not folder_request("create folder X on desktop and close Chrome")


@pytest.mark.asyncio
@pytest.mark.parametrize("combined", [True, False])
async def test_folder_then_mail_keeps_recipient_and_body(desktop_engine, monkeypatch, combined):
    from awareness.gmail import GmailMailbox
    engine, desktop = desktop_engine
    create = MagicMock(return_value="Gmail draft saved.")
    monkeypatch.setattr(GmailMailbox, "compose", create)
    async def command(text):
        return await engine.command(text, RunControl(), AsyncMock(), MagicMock())
    folder = "create a folder named Parthz on desktop"
    mail = "send a mail to my friend"
    if combined:
        reply = await command(folder + " and then " + mail)
        assert 'Created folder' in reply
    else:
        assert "Created folder" in await command(folder)
        reply = await command(mail)
    assert "email address" in reply and (desktop / "Parthz").is_dir()
    assert "friend@example.org" in await command("her email ID is friend at example dot org")
    assert "What should" in await command("yes")
    assert "Gmail draft saved" in await command("See you at six.")
    assert create.call_args.args[:2] == ("draft", ("friend@example.org", "Message", "See you at six."))
    assert len(list(desktop.iterdir())) == 1


@pytest.mark.asyncio
async def test_failed_folder_blocks_mail_step(desktop_engine):
    engine, desktop = desktop_engine
    (desktop / "Taken").write_text("existing")
    reply = await engine.command("create folder Taken on desktop then send an email to alex@example.org",
                                 RunControl(), AsyncMock(), MagicMock())
    assert "email" not in reply.lower()
    assert engine.brain.gmail_mailbox is None


@pytest.mark.asyncio
async def test_folder_acknowledgement_cannot_become_a_folder_name(desktop_engine):
    engine, desktop = desktop_engine
    await engine.command("create a folder on desktop", RunControl(), AsyncMock(), MagicMock())
    reply = await engine.command("yes", RunControl(), AsyncMock(), MagicMock())
    assert "name" in reply and not list(desktop.iterdir())


@pytest.mark.asyncio
async def test_screen_request_interrupts_a_coding_clarification(desktop_engine, monkeypatch):
    from brain.coding_intent import CodingIntent
    engine, _ = desktop_engine
    engine.coding_intent = CodingIntent()
    engine.coding_intent.pending_goal = 'Fix the script in "C:/Project".'
    analyze = AsyncMock(return_value={"message": "Screen checked."})
    monkeypatch.setattr(engine.brain.vision, "analyze_screen", analyze)
    assert await engine.command("read my screen", RunControl(), AsyncMock(), MagicMock()) == "Screen checked."
    assert engine.coding_intent.pending_goal == ""
    analyze.assert_awaited_once()
