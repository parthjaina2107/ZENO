"""
Unit tests for ActionPlanner risk table, validation, and honest confirmations.
"""

import pytest
from brain.planner import ActionPlanner, PlannedAction
from config import config


def test_risk_table_llm_cannot_lower_risk():
    planner = ActionPlanner()
    # High risk action reported as low by LLM
    nlu_data = {
        "understood": True,
        "action": "run_command",
        "parameters": {"command": "dir"},
        "description": "Run dir command",
        "risk_level": "low",
        "confirmation_message": "Run dir?"
    }
    actions = planner.plan(nlu_data)
    assert len(actions) == 1
    assert actions[0].action_type == "run_command"
    assert actions[0].risk_level == "high"


def test_risk_table_llm_can_raise_risk():
    planner = ActionPlanner()
    # Low risk action raised to high by LLM
    nlu_data = {
        "understood": True,
        "action": "open_app",
        "parameters": {"app_name": "danger_app"},
        "description": "Open dangerous app",
        "risk_level": "high",
        "confirmation_message": "Open danger_app?"
    }
    actions = planner.plan(nlu_data)
    assert len(actions) == 1
    assert actions[0].action_type == "open_app"
    assert actions[0].risk_level == "high"


def test_unknown_action_rejected_as_unhandled():
    planner = ActionPlanner()
    nlu_data = {
        "understood": True,
        "action": "unknown_exploit_action",
        "parameters": {"data": 123},
        "description": "Unknown exploit",
        "risk_level": "low"
    }
    actions = planner.plan(nlu_data)
    assert len(actions) == 1
    assert actions[0].action_type == "unhandled"
