import asyncio
import json
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from desktop.control import RunControl
from desktop.settings import DesktopSettings
from desktop.engine import DesktopEngine
from brain.planner import ActionPlanner, ActionResult
from brain.task_runner import TaskRunner


def test_settings_round_trip_and_corrupt_file(tmp_path):
    path = tmp_path / "desktop.json"
    settings = DesktopSettings("Ctrl+Alt+Z", False, 3)
    settings.save(path)
    assert DesktopSettings.load(path) == settings
    assert not path.with_suffix(".tmp").exists()
    for content in ("oops", "[]", '{"shortcut":7,"microphone":true}'):
        path.write_text(content)
        assert DesktopSettings.load(path) == DesktopSettings()


def test_desktop_listener_never_opens_mic_at_init(monkeypatch):
    import speech_recognition as sr
    from voice.listener import VoiceListener
    microphone = MagicMock(side_effect=AssertionError("Microphone must stay closed"))
    monkeypatch.setattr(sr, "Microphone", microphone)
    listener = VoiceListener(initialize_microphone=False)
    assert listener._recognizer is not None
    microphone.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_reasoning_does_not_return_late_result():
    token = RunControl()
    cleanup = []
    async def reasoning():
        try:
            await asyncio.sleep(60)
            return "execute something"
        finally:
            cleanup.append(True)
    task = asyncio.create_task(token.wait(reasoning()))
    await asyncio.sleep(0.01)
    token.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 1)
    assert cleanup == [True]


@pytest.mark.asyncio
async def test_cancel_drains_started_os_action():
    token = RunControl()
    entered, release = threading.Event(), threading.Event()
    calls = []
    def first():
        entered.set()
        release.wait(2)
        calls.append("first")
    async def execute():
        await token.call(first)
        token.check()
        await token.call(lambda: calls.append("second"))
    task = asyncio.create_task(execute())
    while not entered.is_set():
        await asyncio.sleep(0.01)
    token.cancel()
    await asyncio.sleep(0.06)
    assert not task.done()  # No new request while the OS thread can still mutate.
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls == ["first"]


@pytest.mark.asyncio
async def test_cancel_before_thread_call_never_executes():
    token = RunControl()
    token.cancel()
    action = MagicMock()
    with pytest.raises(asyncio.CancelledError):
        await token.call(action)
    with pytest.raises(asyncio.CancelledError):
        token.immediate(action)
    action.assert_not_called()


def fake_engine():
    engine = DesktopEngine.__new__(DesktopEngine)
    engine.brain = MagicMock()
    engine.brain.client = None
    engine.brain.think = AsyncMock()
    engine.permissions = MagicMock()
    engine.speaker = MagicMock()
    engine.speaker.is_busy = False
    engine.listener = MagicMock()
    engine.awareness = None
    return engine


@pytest.mark.asyncio
async def test_direct_actions_stop_before_next_step():
    token = RunControl()
    engine = fake_engine()
    actions = [SimpleNamespace(action_type="open_app", requires_permission=False,
               description="Open Notepad", parameters={"app_name": "notepad"})] * 2
    engine.brain.think.return_value = SimpleNamespace(kind="action", actions=actions)
    def execute(action):
        token.cancel()
        return ActionResult(True, "Opened")
    engine.brain.planner.execute_action.side_effect = execute
    with pytest.raises(asyncio.CancelledError):
        await engine.command("open notepad twice", token, AsyncMock(), MagicMock())
    assert engine.brain.planner.execute_action.call_count == 1


@pytest.mark.asyncio
async def test_cancel_pending_approval_never_executes():
    token = RunControl()
    engine = fake_engine()
    engine.brain.think.return_value = SimpleNamespace(kind="action", actions=[
        SimpleNamespace(action_type="file_delete", requires_permission=True)])
    async def approve(action):
        token.cancel()
        return True
    with pytest.raises(asyncio.CancelledError):
        await engine.command("delete", token, approve, MagicMock())
    engine.brain.planner.execute_action.assert_not_called()


@pytest.mark.asyncio
async def test_task_runner_cancellation_saves_report_no_next_step(tmp_path, monkeypatch):
    from config import config
    monkeypatch.setattr(config, "BASE_DIR", tmp_path)
    token = RunControl()
    brain = MagicMock()
    brain.planner = ActionPlanner(MagicMock())
    runner = TaskRunner(brain, MagicMock())
    runner.decide = AsyncMock(return_value={"action": "system_info", "parameters": {"info_type": "battery"}})
    runner.preflight = MagicMock()
    runner.verify = MagicMock(return_value=(True, "Observed"))
    def execute(action):
        token.cancel()
        return ActionResult(True, "Battery available")
    brain.planner.execute_action = MagicMock(side_effect=execute)
    with pytest.raises(asyncio.CancelledError):
        await runner.run("battery", AsyncMock(), AsyncMock(), control=token)
    assert brain.planner.execute_action.call_count == 1
    report = json.loads(next((tmp_path / "task_reports").glob("*.json")).read_text())
    assert report["status"] == "cancelled" and len(report["steps"]) == 1


@pytest.mark.asyncio
async def test_uncertain_audio_requires_typed_review(monkeypatch):
    from desktop import audio
    monkeypatch.setattr(audio, "capture", MagicMock(return_value=object()))
    engine = fake_engine()
    engine.listener._transcribe_audio.return_value = "delete something"
    engine.listener.last_uncertain = True
    emit = MagicMock()
    result = await engine.run(None, RunControl(), AsyncMock(), emit, DesktopSettings())
    assert "not confident" in result
    engine.brain.think.assert_not_awaited()
    emit.assert_any_call("draft", "delete something")


def test_capture_closes_stream_on_cancel(monkeypatch):
    import speech_recognition as sr
    from desktop.audio import capture
    token = RunControl()
    source = MagicMock()
    source.CHUNK = 512
    source.SAMPLE_RATE = 16000
    source.SAMPLE_WIDTH = 2
    def read(size):
        token.cancel()
        return b"\x00" * 1024
    source.stream.read.side_effect = read
    microphone = MagicMock()
    microphone.__enter__.return_value = source
    monkeypatch.setattr(sr, "Microphone", MagicMock(return_value=microphone))
    with pytest.raises(asyncio.CancelledError):
        capture(token)
    microphone.__exit__.assert_called_once()


def test_capture_cancelled_before_open_never_touches_mic(monkeypatch):
    import speech_recognition as sr
    from desktop.audio import capture
    microphone = MagicMock()
    monkeypatch.setattr(sr, "Microphone", microphone)
    token = RunControl()
    token.cancel()
    with pytest.raises(asyncio.CancelledError):
        capture(token)
    microphone.assert_not_called()


def test_pause_preferences_validate_and_preserve_old_settings(tmp_path):
    path = tmp_path / "desktop.json"
    path.write_text('{"shortcut":"F8"}')
    assert DesktopSettings.load(path).pause_seconds == 0.6
    for value in (None, [], "fast", -1, 120):
        path.write_text(json.dumps({"pause_seconds": value}))
        assert DesktopSettings.load(path).pause_seconds == 0.6
    settings = DesktopSettings(pause_seconds=1.4)
    settings.save(path)
    assert DesktopSettings.load(path).pause_seconds == 1.4


def test_capture_endpoint_and_meter(monkeypatch):
    import speech_recognition as sr
    import struct
    from desktop import audio
    def record(pause):
        clock = iter(i * 0.1 for i in range(100))
        monkeypatch.setattr(audio.time, "monotonic", lambda: next(clock))
        source = MagicMock(CHUNK=512, SAMPLE_RATE=16000, SAMPLE_WIDTH=2)
        source.stream.read.side_effect = [struct.pack("<512h", *([1000] * 512))] + [b"\x00" * 1024] * 50
        microphone = MagicMock()
        microphone.__enter__.return_value = source
        monkeypatch.setattr(sr, "Microphone", MagicMock(return_value=microphone))
        levels = []
        result = audio.capture(RunControl(), pause_seconds=pause, on_level=levels.append)
        microphone.__exit__.assert_called_once()
        assert levels[0] > 0 and levels[-1] == 0
        assert result.sample_rate == 16000
        return source.stream.read.call_count
    assert record(0.6) < record(1.4)


@pytest.mark.asyncio
async def test_model_load_overlaps_capture_before_transcription(monkeypatch):
    from desktop import audio
    engine = fake_engine()
    entered, loaded = threading.Event(), threading.Event()
    def capture(*args, **kwargs):
        entered.set()
        assert loaded.wait(2), "Model load must overlap microphone capture"
        kwargs["on_level"](0.5)
        return "audio"
    def load():
        assert entered.wait(2)
        loaded.set()
    monkeypatch.setattr(audio, "capture", capture)
    engine.listener._get_whisper_model.side_effect = load
    engine.listener._transcribe_audio.return_value = "hello"
    engine.listener.last_uncertain = False
    engine.brain.think.return_value = SimpleNamespace(kind="chat", message="Hi")
    emit = MagicMock()
    await engine.run(None, RunControl(), AsyncMock(), emit, DesktopSettings(spoken_replies=False))
    engine.listener._transcribe_audio.assert_called_once_with("audio")
    emit.assert_any_call("level", "0.5")


def test_overlay_lifecycle_and_no_focus():
    pytest.importorskip("PySide6")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from desktop.overlay import ActivityOverlay
    app = QApplication.instance() or QApplication([])
    overlay = ActivityOverlay()
    try:
        assert overlay.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
        assert overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput
        overlay.handle_event("state", "Preparing")
        assert overlay.isVisible()
        overlay.handle_event("state", "Listening")
        overlay.handle_event("level", "0.8")
        assert overlay.bars.level == 0.8
        overlay.handle_event("state", "Thinking")
        assert overlay.bars.level == 0
        overlay.handle_event("reply", "Opened Notepad.")
        overlay.handle_event("state", "Ready")
        assert overlay.dismiss.isActive() and not overlay.bars.timer.isActive()
        overlay.handle_event("state", "Preparing")
        assert not overlay.dismiss.isActive()
        assert "shortcut" in overlay.caption.text()
        app.processEvents()
    finally:
        overlay.close()


def test_shortcut_validation_and_conflict_preserves_old():
    pytest.importorskip("PySide6")
    from desktop.hotkey import GlobalHotkey, parse_shortcut
    assert parse_shortcut("Ctrl+Alt+Z") == (0x4003, ord("Z"))
    assert parse_shortcut("F8") == (0x4000, 0x77)
    for text in ("Z", "Shift+X", "F12", "Win+Z", "Ctrl+C", "Alt+F4", "Ctrl+Ctrl+Q", ""):
        with pytest.raises(ValueError):
            parse_shortcut(text)
    application, api = MagicMock(), MagicMock()
    api.RegisterHotKey.side_effect = [True, False, True]
    binding = GlobalHotkey(application, MagicMock(), api=api)
    binding.register("Ctrl+Alt+Z")
    with pytest.raises(ValueError):
        binding.register("Ctrl+Alt+X")
    assert binding.binding == "Ctrl+Alt+Z"
    api.UnregisterHotKey.assert_not_called()
    binding.register("Ctrl+Alt+A")
    api.UnregisterHotKey.assert_called_once_with(None, 0x5A01)
    binding.close()
    assert binding.active_id is None


@pytest.mark.asyncio
async def test_speech_stop_interrupts_without_listening():
    engine = fake_engine()
    engine.brain.think.return_value = SimpleNamespace(kind="chat", message="Hello")
    token = RunControl()
    engine.speaker.is_busy = True
    def interrupt():
        engine.speaker.is_busy = False
    engine.speaker.interrupt.side_effect = interrupt
    engine.speaker.speak.side_effect = lambda text: asyncio.get_running_loop().call_soon(token.cancel)
    with pytest.raises(asyncio.CancelledError):
        await engine.run("hi", token, AsyncMock(), MagicMock(), DesktopSettings())
    engine.speaker.interrupt.assert_called()
    engine.listener._transcribe_audio.assert_not_called()


@pytest.mark.asyncio
async def test_controller_same_activation_stops_and_never_spawns_twice(monkeypatch):
    pytest.importorskip("PySide6")
    from desktop.controller import DesktopController
    threads = MagicMock()
    monkeypatch.setattr("desktop.controller.threading.Thread", threads)
    controller = DesktopController(DesktopSettings())
    controller.activate()
    first = controller.control
    controller.activate()
    controller.activate()
    assert controller.busy and first.cancelled.is_set()
    assert threads.call_count == 1
    controller._finished()
    controller.activate()
    assert controller.control is not first
    assert not controller.control.cancelled.is_set()
    assert threads.call_count == 2


@pytest.mark.asyncio
async def test_high_risk_approval_needs_two_unique_responses():
    pytest.importorskip("PySide6")
    from desktop.controller import DesktopController
    controller = DesktopController(DesktopSettings())
    controller.engine = fake_engine()
    controller.control = token = RunControl()
    action = SimpleNamespace(action_type="power_control", parameters={"action": "restart"},
                             risk_level="high", description="Restart")
    task = asyncio.create_task(controller._approve(action, token))
    await asyncio.sleep(0)
    first_id = controller.pending_id
    controller.answer_approval(first_id, True)
    await asyncio.sleep(0.08)
    second_id = controller.pending_id
    assert first_id and second_id and first_id != second_id
    controller.answer_approval(first_id, True)  # Stale first approval is ignored.
    await asyncio.sleep(0.06)
    assert not task.done()
    controller.answer_approval(second_id, True)
    assert await asyncio.wait_for(task, 1) is True
    assert controller.pending_id is None
    controller.engine.permissions.log_decision.assert_called_once_with(action, True, source="desktop")


@pytest.mark.asyncio
async def test_controller_cancellation_invalidates_pending_approval():
    pytest.importorskip("PySide6")
    from desktop.controller import DesktopController
    controller = DesktopController(DesktopSettings())
    controller.engine = fake_engine()
    controller.control = token = RunControl()
    action = SimpleNamespace(action_type="file_delete", parameters={"path": "example.txt"},
                             risk_level="high", description="Delete example")
    task = asyncio.create_task(controller._approve(action, token))
    await asyncio.sleep(0)
    pending_id = controller.pending_id
    token.cancel()
    controller.answer_approval(pending_id, True)
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 1)
    assert controller.pending_id is None
    controller.engine.permissions.log_decision.assert_called_once_with(action, False, source="desktop")
