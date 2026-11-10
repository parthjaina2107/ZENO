from unittest.mock import MagicMock

import pytest

import app_access
from awareness.gmail import GmailMailbox
from brain.planner import PlannedAction
from brain.vision import ScreenVision
from config import config
from executor.task_executor import TaskExecutor


def test_new_profile_starts_off_and_app_grants_are_independent(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "fresh")
    executor = TaskExecutor()
    executor.system.open_app = MagicMock()
    chrome = PlannedAction("open_app", {"app_name": "Google Chrome"})
    assert not executor.execute(chrome).success
    app_access.set_choice("chrome", True)
    assert app_access.allowed("chrome") and not app_access.allowed("edge")
    executor.execute(chrome)
    executor.system.open_app.assert_called_once_with("Google Chrome")
    app_access.set_choice("chrome", False)
    assert executor.execute(chrome).error == "ACCESS_DISABLED"
    assert executor.system.open_app.call_count == 1


@pytest.mark.asyncio
async def test_disabling_screen_or_mail_denies_before_provider_access(monkeypatch):
    app_access.set_choice("screen", False)
    vision = ScreenVision()
    monkeypatch.setattr(vision, "capture_screen", MagicMock(side_effect=AssertionError))
    assert not (await vision.analyze_screen("read my screen"))["success"]
    app_access.set_choice("gmail_send", False)
    assert app_access.allowed("gmail_read")
    box = GmailMailbox()
    box.pending = ("654321", "dummy", "v", "text")
    assert "is off" in await box.respond(("send_draft", "654321"), None)
    assert box.pending is None


def test_notification_with_mail_app_name_uses_notification_permission(tmp_path):
    from awareness.sources import event
    from awareness.service import AwarenessService
    from awareness.store import EventStore
    store = EventStore(tmp_path / "events.sqlite3")
    store.add(event("Gmail", "a" * 64, "Legacy toast"))
    store.add(event("Gmail", "toast", "Current toast"), feature="notifications")
    store.add(event("Gmail", "message", "Mailbox result"), feature="gmail_read")
    app_access.set_choice("notifications", False)
    service = AwarenessService(store, [])
    assert [item["title"] for item in service._events()] == ["Mailbox result"]
    app_access.set_choice("notifications", True)
    app_access.set_choice("gmail_read", False)
    assert {item["title"] for item in service._events()} == {"Legacy toast", "Current toast"}


def test_file_tools_cannot_replace_dashboard_access_choices(tmp_path, monkeypatch):
    from executor.file_ops import FileOps
    settings_dir = tmp_path / "private"
    settings_dir.mkdir()
    monkeypatch.setattr(config, "DATA_DIR", settings_dir)
    ops = FileOps([str(tmp_path)])
    candidate = tmp_path / "app-access.json"
    candidate.write_text('{"power": true}')
    assert not ops.file_create(str(settings_dir / candidate.name), candidate.read_text()).success
    assert not ops.file_move(str(candidate), str(settings_dir)).success
    assert not ops.file_copy(str(candidate), str(settings_dir)).success
    assert not ops.file_delete(str(settings_dir), permanent=True).success
    assert not app_access.allowed("power")


@pytest.mark.asyncio
async def test_cloud_grant_takes_effect_on_existing_brain_and_revocation_blocks_requests(monkeypatch):
    from google import genai
    from brain.api_utils import call_gemini_with_fallback
    from brain.zeno_brain import ZenoBrain
    app_access.set_choice("cloud_ai", False)
    client = MagicMock()
    client.models.generate_content.return_value.text = "Mocked reply"
    monkeypatch.setattr(genai, "Client", MagicMock(return_value=client))
    brain = ZenoBrain(api_key="test-key")
    assert brain.client is client and brain.vision.client is client and brain.nlu.client is client
    assert await call_gemini_with_fallback(brain.client, "hello") is None
    client.models.generate_content.assert_not_called()
    app_access.set_choice("cloud_ai", True)
    assert (await call_gemini_with_fallback(brain.client, "hello")).text == "Mocked reply"
    app_access.set_choice("cloud_ai", False)
    assert await call_gemini_with_fallback(brain.client, "hello") is None
    client.models.generate_content.assert_called_once()
