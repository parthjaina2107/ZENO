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


@pytest.mark.asyncio
async def test_nlu_known_websites():
    engine = NLUEngine(api_key="")
    # Direct website
    res1 = await engine.understand("open youtube")
    assert res1["understood"] is True
    assert res1["action"] == "open_url"
    assert res1["parameters"]["url"] == "https://www.youtube.com"

    # Website with browser context
    res2 = await engine.understand("open youtube in chrome browser")
    assert res2["understood"] is True
    assert res2["action"] == "open_url"
    assert res2["parameters"]["url"] == "https://www.youtube.com"

    # GitHub
    res3 = await engine.understand("open github")
    assert res3["understood"] is True
    assert res3["action"] == "open_url"
    assert res3["parameters"]["url"] == "https://github.com"


@pytest.mark.asyncio
async def test_nlu_conversational_bypass():
    engine = NLUEngine(api_key="")
    res = await engine.understand("what is machine learning?")
    assert res["understood"] is False
    assert res["action"] == "none"


@pytest.mark.asyncio
async def test_api_utils_fallback_retry():
    from unittest.mock import MagicMock
    from brain.api_utils import call_gemini_with_fallback

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = '{"understood": true, "action": "system_info"}'

    # First call on gemini-3.8-flash raises 503, second call succeeds on fallback model
    call_counts = {"attempts": 0}

    def fake_generate(model, contents):
        call_counts["attempts"] += 1
        if model == "gemini-3.8-flash":
            raise Exception("503 Service Unavailable")
        return mock_resp

    mock_client.models.generate_content.side_effect = fake_generate

    resp = await call_gemini_with_fallback(
        client=mock_client,
        contents="test prompt",
        primary_model="gemini-3.8-flash",
        max_retries=1
    )

    assert resp is not None
    assert resp.text == '{"understood": true, "action": "system_info"}'
    assert call_counts["attempts"] >= 2


@pytest.mark.asyncio
async def test_nlu_misroutes_prevented():
    engine = NLUEngine(api_key="")
    # 1. "open instagram" -> not RAM usage
    r1 = await engine.understand("open instagram")
    assert not (r1["understood"] and r1.get("action") == "system_info" and r1.get("parameters", {}).get("type") == "ram")
    assert r1.get("action") in ("open_url", "open_app")

    # 2. "open telegram" -> not RAM usage
    r2 = await engine.understand("open telegram")
    assert not (r2["understood"] and r2.get("action") == "system_info" and r2.get("parameters", {}).get("type") == "ram")
    assert r2.get("action") in ("open_url", "open_app")

    # 3. "update my resume" -> not time
    r3 = await engine.understand("update my resume")
    assert not (r3["understood"] and r3.get("action") == "system_info" and r3.get("parameters", {}).get("type") == "time")

    # 4. "skip this song" -> not IP address
    r4 = await engine.understand("skip this song")
    assert not (r4["understood"] and r4.get("action") == "system_info" and r4.get("parameters", {}).get("type") == "ip")

    # 5. "open program files" -> not RAM usage
    r5 = await engine.understand("open program files")
    assert not (r5["understood"] and r5.get("action") == "system_info" and r5.get("parameters", {}).get("type") == "ram")

    # 6. "block my screen" -> not lock workstation
    r6 = await engine.understand("block my screen")
    assert not (r6["understood"] and r6.get("action") == "shutdown" and r6.get("parameters", {}).get("mode") == "lock")
