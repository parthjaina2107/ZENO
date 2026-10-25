"""Task behavior tests. No microphone, real desktop mutations or model calls."""
import asyncio
import copy
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from brain.agent import AgentDecision, AgentStep, GoalPlanner
from brain.nlu import NLUEngine
from brain.planner import ActionPlanner, ActionResult
from brain.zeno_brain import ZenoBrain
from config import config
from executor.agent_runner import AgentRunner, coordinator
from executor.permissions import PermissionManager


def step(action, **parameters):
    return AgentStep(action=action, parameters=parameters)


def plan(*steps):
    return AgentDecision(status="plan", message="Task ready", steps=list(steps))


@pytest.fixture
def rig(tmp_path):
    executor = MagicMock()
    executor.execute.return_value = ActionResult(True, "Executed", {"value": 42})
    nlu = NLUEngine(api_key="")
    planner = ActionPlanner(executor)
    brain = SimpleNamespace(planner=planner, goal_planner=GoalPlanner(nlu, planner), memory=MagicMock())
    permissions = PermissionManager(audit_log_path=str(tmp_path / "audit.jsonl"))
    events = []
    async def emit(event):
        events.append(copy.deepcopy(event))
    approve = AsyncMock(return_value=True)
    runner = AgentRunner(brain, permissions, "test", approve, emit)
    yield SimpleNamespace(**locals())
    assert coordinator.active is None


@pytest.mark.asyncio
async def test_compound_commands_and_literal_case():
    nlu = NLUEngine(api_key="")
    result = await nlu.understand('open notepad then type "Hello ZENO and then Goodbye"')
    assert result["action"] == "multi_step"
    assert [s["action"] for s in result["parameters"]["steps"]] == ["open_app", "type_text"]
    assert result["parameters"]["steps"][1]["parameters"]["text"] == "Hello ZENO and then Goodbye"
    typed = await nlu.understand("type Bread and Butter then Jam")
    assert typed["parameters"]["text"] == "Bread and Butter then Jam"
    url = await nlu.understand("open https://example.com/CaseSensitive")
    assert url["parameters"]["url"].endswith("/CaseSensitive")


@pytest.mark.asyncio
async def test_unknown_tail_never_executes_prefix():
    result = await NLUEngine(api_key="").understand("open notepad then frobnicate everything")
    assert result["understood"] is False


def test_nested_dangerous_command_is_blocked():
    nlu = NLUEngine(api_key="")
    result = nlu._sanitize_command({"understood": True, "action": "multi_step", "parameters": {
        "steps": [{"action": "open_app", "parameters": {"app_name": "notepad"}},
                  {"action": "run_command", "parameters": {"command": "format C:"}}]}})
    assert result["understood"] is False


@pytest.mark.asyncio
async def test_offline_voice_task_runs_entire_sequence(rig):
    await rig.runner.run("open notepad then type Hello ZENO", agent_mode=True)
    assert [c.args[0].action_type for c in rig.executor.execute.call_args_list] == ["open_app", "type_text"]
    assert rig.approve.await_count == 1
    batch = rig.approve.call_args.args[0]
    assert batch.action_type == "task_plan"
    assert batch.parameters["steps"][0]["parameters"]["text"] == "Hello ZENO"
    assert rig.events[-1]["status"] == "completed"


@pytest.mark.asyncio
async def test_denied_plan_runs_nothing(rig):
    rig.approve.return_value = False
    await rig.runner.run("open notepad then type hello", agent_mode=True)
    rig.executor.execute.assert_not_called()
    assert rig.events[-1]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_preflight_rejects_entire_invalid_phase(rig):
    rig.brain.goal_planner.decide = AsyncMock(return_value=plan(step("open_app", app_name="notepad"), step("volume_set", level=200)))
    await rig.runner.run("test", agent_mode=True)
    rig.executor.execute.assert_not_called()
    assert rig.events[-1]["status"] == "failed"


@pytest.mark.asyncio
async def test_results_feed_the_next_plan(rig):
    snapshots = []
    async def decide(goal, observations):
        snapshots.append(copy.deepcopy(observations))
        if not observations:
            return plan(step("file_search", directory="Desktop", pattern="*.txt"))
        if len(observations) == 1:
            return plan(step("file_read", path="Desktop/found.txt"))
        return AgentDecision(status="done", message="Read the file found by search.")
    rig.brain.goal_planner.decide = decide
    await rig.runner.run("Find and read my note", agent_mode=True)
    assert len(snapshots) == 3
    assert snapshots[1][0]["success"] is True
    assert '42' in snapshots[1][0]["output"]
    assert rig.events[-1]["status"] == "completed"


@pytest.mark.asyncio
async def test_failure_stops_dependent_steps(rig):
    rig.executor.execute.return_value = ActionResult(False, "App not installed", error="NOT_FOUND")
    await rig.runner.run("open notepad then type hello", agent_mode=True)
    assert rig.executor.execute.call_count == 1
    assert rig.events[-1]["status"] == "blocked"


@pytest.mark.asyncio
async def test_repeated_side_effect_blocked(rig):
    rig.brain.goal_planner.decide = AsyncMock(return_value=plan(step("open_app", app_name="notepad")))
    await rig.runner.run("test", agent_mode=True)
    assert rig.executor.execute.call_count == 1
    assert "repeated" in rig.events[-1]["message"]


@pytest.mark.asyncio
async def test_step_limit_prevents_partial_execution(rig, monkeypatch):
    monkeypatch.setattr(config, "AGENT_MAX_STEPS", 1)
    rig.brain.goal_planner.decide = AsyncMock(return_value=plan(step("open_app", app_name="notepad"), step("volume_set", level=20)))
    await rig.runner.run("test", agent_mode=True)
    rig.executor.execute.assert_not_called()


@pytest.mark.asyncio
async def test_stop_cancels_pending_approval(rig):
    requested = asyncio.Event()
    async def approve(action):
        requested.set()
        await asyncio.Future()
    rig.runner.approve = approve
    running = asyncio.create_task(rig.runner.run("type hello", agent_mode=True))
    await asyncio.wait_for(requested.wait(), 1)
    coordinator.stop()
    await asyncio.wait_for(running, 1)
    rig.executor.execute.assert_not_called()
    assert rig.events[-1]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_keeps_desktop_lock_until_worker_finishes(rig):
    started, finish = threading.Event(), threading.Event()
    def execute(action):
        started.set()
        finish.wait(2)
        return ActionResult(True, "Finished in-flight action")
    rig.executor.execute.side_effect = execute
    running = asyncio.create_task(rig.runner.run("open notepad then open calculator", agent_mode=True))
    assert await asyncio.to_thread(started.wait, 1)
    running.cancel()
    await asyncio.sleep(.03)
    assert coordinator.active is not None
    running.cancel()  # Repeated stop must not release the desktop early.
    await asyncio.sleep(.03)
    assert coordinator.active is not None
    finish.set()
    await asyncio.wait_for(running, 1)
    assert rig.executor.execute.call_count == 1
    assert rig.events[-1]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_model_output_is_validated(rig, monkeypatch):
    rig.nlu.client = object()
    fake = AsyncMock(return_value=SimpleNamespace(text='{"status":"plan","message":"go","steps":[]}'))
    monkeypatch.setattr("brain.agent.call_gemini_with_fallback", fake)
    decision = await rig.brain.goal_planner.decide("test", [])
    assert decision.status == "blocked"
    fake.return_value.text = '{"status":"done","message":"I already did it","steps":[]}'
    decision = await rig.brain.goal_planner.decide("test", [])
    assert decision.status == "blocked"


@pytest.mark.asyncio
async def test_task_routing_and_stop_precedence(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "MEMORY_FILE", str(tmp_path / "memory.json"))
    brain = ZenoBrain(api_key="")
    response = await brain.think("Hey Zeno, task: open notepad then type Hello")
    assert response.kind == "task"
    assert response.data["goal"] == "open notepad then type Hello"
    assert (await brain.think("stop", agent_mode=True)).kind == "abort"


@pytest.mark.asyncio
async def test_remote_permission_cancel_removes_pending_request(tmp_path):
    perms = PermissionManager(audit_log_path=str(tmp_path / "audit.jsonl"))
    actions = ActionPlanner().plan({"understood": True, "action": "open_app", "parameters": {"app_name": "notepad"}})
    ready = asyncio.Event()
    async def send(payload):
        ready.set()
    task = asyncio.create_task(perms.request_permission_remote(actions[0], send))
    await ready.wait()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert not perms._pending_remote_requests
