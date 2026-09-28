"""
Unit tests for NLU Engine and Action Planner.
"""

import pytest
from brain.nlu import NLUEngine
from brain.planner import ActionPlanner, PlannedAction


@pytest.mark.asyncio
async def test_nlu_system_info():
    engine = NLUEngine(api_key="")  # uses fallback
    res = await engine.understand("What is my battery level?")
    assert res["understood"] is True
    assert res["action"] == "system_info"
    assert res["parameters"]["type"] == "battery"
    assert res["risk_level"] == "low"


@pytest.mark.asyncio
async def test_nlu_screenshot():
    engine = NLUEngine(api_key="")
    res = await engine.understand("take a screenshot please")
    assert res["understood"] is True
    assert res["action"] == "screenshot"


@pytest.mark.asyncio
async def test_nlu_blocked_command():
    engine = NLUEngine(api_key="")
    res = await engine.understand("run command format c:")
    # Either blocked by regex or understood with safety flag
    sanitized = engine._sanitize_command({
        "understood": True,
        "action": "run_command",
        "parameters": {"command": "format C:"}
    })
    assert sanitized["understood"] is False
    assert sanitized["action"] == "blocked"


def test_action_planner():
    planner = ActionPlanner()
    nlu_data = {
        "understood": True,
        "action": "open_app",
        "parameters": {"app_name": "chrome"},
        "description": "Open Chrome browser",
        "risk_level": "low",
        "confirmation_message": "Open Chrome?"
    }
    actions = planner.plan(nlu_data)
    assert len(actions) == 1
    assert actions[0].action_type == "open_app"
    assert actions[0].requires_permission is True
