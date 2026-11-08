"""Local voice approval and TTS rejection without real audio devices."""
import asyncio
from unittest.mock import MagicMock

import pytest
from brain.planner import PlannedAction
from executor.permissions import PermissionManager
from main import VoiceAgentApp
from voice.listener import VoiceListener


@pytest.mark.asyncio
async def test_local_high_risk_approval_waits_for_two_distinct_replies(tmp_path):
    app = VoiceAgentApp.__new__(VoiceAgentApp)
    app._local_approval = None
    app.speaker = MagicMock()
    app.permissions = PermissionManager(audit_log_path=str(tmp_path / "audit.jsonl"))
    action = PlannedAction("run_command", {"command": "whoami"}, risk_level="high")
    task = asyncio.create_task(app.approve_local_task(action))
    await asyncio.sleep(0)
    first = app._local_approval
    first.set_result(True)
    for _ in range(10):
        await asyncio.sleep(0)
        if app._local_approval is not first:
            break
    assert not task.done()
    assert app._local_approval is not first
    app._local_approval.set_result(False)
    assert await task is False
    assert app._local_approval is None


def test_capture_overlapping_tts_is_discarded():
    listener = VoiceListener.__new__(VoiceListener)
    listener._mic_available = True
    listener._microphone = MagicMock()
    listener._recognizer = MagicMock()
    listener._transcribe_audio = MagicMock(return_value="yes")
    listener.tts_state = MagicMock(side_effect=[(1, False), (2, False)])
    assert listener.listen_once() is None
    listener._transcribe_audio.assert_not_called()


@pytest.mark.asyncio
async def test_local_loop_listens_for_stop_during_execution():
    app = VoiceAgentApp.__new__(VoiceAgentApp)
    app.running = True
    from voice.conversation import ConversationSession
    app.conversation = ConversationSession(wake_enabled=False)
    app._local_task = None
    app._local_approval = None
    app.speaker = MagicMock()
    app.brain = MagicMock()
    app.brain.strip_wake_prefix.side_effect = lambda text: text
    started = asyncio.Event()
    cancelled = asyncio.Event()
    async def command(text):
        started.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.set()
    app.process_user_command = command
    phrases = iter(["task open notepad", "stop"])
    def listen(*args):
        phrase = next(phrases, None)
        if phrase is None:
            app.running = False
        return phrase
    app.listener = MagicMock()
    app.listener.listen_once.side_effect = listen
    app.listener.last_uncertain = False
    await asyncio.wait_for(app.run_local_loop(), 2)
    assert started.is_set()
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_cancelled_local_call_keeps_ownership_until_worker_returns():
    import threading
    from unittest.mock import AsyncMock
    from executor.agent_runner import coordinator
    from brain.planner import ActionResult
    app = VoiceAgentApp.__new__(VoiceAgentApp)
    app.speaker = MagicMock()
    app.permissions = MagicMock()
    app.brain = MagicMock()
    action = PlannedAction("system_info", {"type": "battery"}, requires_permission=False)
    app.brain.think = AsyncMock(return_value=MagicMock(kind="action", actions=[action, action]))
    app.planner = MagicMock()
    started, release = threading.Event(), threading.Event()
    def worker(action):
        started.set()
        assert release.wait(5)
        return ActionResult(True, "Observed")
    app.planner.execute_action.side_effect = worker
    task = asyncio.create_task(app.process_user_command("local probe"))
    try:
        assert await asyncio.to_thread(started.wait, 3)
        task.cancel()
        await asyncio.sleep(0.05)
        assert coordinator.active.source == "local" and not task.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    app.planner.execute_action.assert_called_once()
    assert coordinator.active is None


@pytest.mark.parametrize("flag", ["-b", "--background"])
def test_legacy_launcher_arguments_reach_the_cli(flag, monkeypatch):
    import main
    agent = MagicMock()
    monkeypatch.setattr(main, "VoiceAgentApp", agent)
    monkeypatch.setattr("brain.ollama_runtime.start_local_runtime", lambda: None)
    monkeypatch.setattr("sys.argv", ["main.py", "--mode", "all", flag, "--port", "4321"])
    main.main()
    agent.assert_called_once_with(mode="all", port=4321)
    agent.return_value.run.assert_called_once()
