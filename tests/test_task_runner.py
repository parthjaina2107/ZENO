from unittest.mock import MagicMock, AsyncMock
import pytest
from brain.planner import ActionPlanner, ActionResult
from brain.task_runner import TaskRunner
from executor.task_executor import TaskExecutor
from executor.file_ops import FileOps


def runner(tmp_path, monkeypatch, decisions):
    from config import config
    monkeypatch.setattr(config, "BASE_DIR", tmp_path)
    executor = TaskExecutor()
    executor.file = FileOps(allowed_dirs=[str(tmp_path)])
    brain = MagicMock()
    brain.planner = ActionPlanner(executor)
    engine = TaskRunner(brain, MagicMock())
    engine.decide = AsyncMock(side_effect=decisions)
    return engine


@pytest.mark.asyncio
async def test_task_creates_reads_and_verifies_real_file(tmp_path, monkeypatch):
    path = str(tmp_path / "report.txt")
    engine = runner(tmp_path, monkeypatch, [
        {"action": "file_create", "parameters": {"path": path, "content": "Hello ZENO"}},
        {"action": "file_read", "parameters": {"path": path}},
        {"finish": True, "message": "Saved"},
    ])
    approve = AsyncMock(return_value=False)
    report = await engine.run("Create and read a report", approve, AsyncMock())
    assert report.status == "completed"
    assert (tmp_path / "report.txt").read_text() == "Hello ZENO"
    assert all(step["verified"] for step in report.steps)
    approve.assert_not_called()


@pytest.mark.asyncio
async def test_task_cannot_overwrite_existing_file(tmp_path, monkeypatch):
    path = tmp_path / "existing.txt"
    path.write_text("Original")
    engine = runner(tmp_path, monkeypatch, [{"action": "file_create", "parameters": {"path": str(path), "content": "Changed"}}])
    report = await engine.run("Save a report", AsyncMock(), AsyncMock())
    assert report.status == "failed"
    assert path.read_text() == "Original"


@pytest.mark.asyncio
async def test_task_deletion_denial_preserves_file(tmp_path, monkeypatch):
    path = tmp_path / "keep.txt"
    path.write_text("Keep")
    engine = runner(tmp_path, monkeypatch, [{"action": "file_delete", "parameters": {"path": str(path)}}])
    approval = AsyncMock(return_value=False)
    report = await engine.run("Delete the file", approval, AsyncMock())
    assert report.status == "cancelled" and path.exists()
    approval.assert_awaited_once()


@pytest.mark.asyncio
async def test_model_finish_without_evidence_is_not_success(tmp_path, monkeypatch):
    engine = runner(tmp_path, monkeypatch, [{"finish": True, "message": "Everything is done!"}])
    report = await engine.run("Do something", AsyncMock(), AsyncMock())
    assert report.status == "unverified"
    assert "Everything is done" not in report.summary()


@pytest.mark.asyncio
async def test_unknown_action_and_repeated_action_stop(tmp_path, monkeypatch):
    for decisions in [
        [{"action": "invented_action", "parameters": {}}],
        [{"action": "file_create", "parameters": {"path": str(tmp_path / "a.txt"), "content": "a"}}] * 2,
    ]:
        engine = runner(tmp_path, monkeypatch, decisions)
        report = await engine.run("Do task", AsyncMock(), AsyncMock())
        assert report.status == "failed"


@pytest.mark.asyncio
async def test_explicit_initial_app_instruction_cannot_be_skipped(tmp_path, monkeypatch):
    engine = runner(tmp_path, monkeypatch, [{"finish": True}])
    engine.brain.planner.executor.system.open_app = MagicMock(return_value=ActionResult(True, "Opened"))
    engine.verify = MagicMock(return_value=(True, "Observed app"))
    report = await engine.run("Open Notepad, then report the result", AsyncMock(), AsyncMock())
    assert report.steps[0]["action"] == "open_app"
    engine.brain.planner.executor.system.open_app.assert_called_once_with("notepad")
