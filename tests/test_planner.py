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
    assert actions[0].requires_permission is False


def test_parameter_validation_volume_valid():
    planner = ActionPlanner()
    nlu_data = {
        "understood": True,
        "action": "volume_set",
        "parameters": {"level": 75},
        "description": "Set volume to 75",
        "risk_level": "low"
    }
    actions = planner.plan(nlu_data)
    assert len(actions) == 1
    assert actions[0].action_type == "volume_set"
    assert actions[0].parameters["level"] == 75


def test_parameter_validation_volume_invalid():
    planner = ActionPlanner()
    # level > 100 is invalid
    nlu_data = {
        "understood": True,
        "action": "volume_set",
        "parameters": {"level": 150},
        "description": "Set volume to 150",
        "risk_level": "low"
    }
    actions = planner.plan(nlu_data)
    assert len(actions) == 1
    assert actions[0].action_type == "unhandled"
    assert actions[0].requires_permission is False


def test_parameter_validation_run_command_invalid():
    planner = ActionPlanner()
    # missing command
    nlu_data = {
        "understood": True,
        "action": "run_command",
        "parameters": {},
        "description": "Run empty command",
        "risk_level": "high"
    }
    actions = planner.plan(nlu_data)
    assert len(actions) == 1
    assert actions[0].action_type == "unhandled"
    assert actions[0].requires_permission is False


def test_parameter_validation_open_app_invalid():
    planner = ActionPlanner()
    # empty app_name
    nlu_data = {
        "understood": True,
        "action": "open_app",
        "parameters": {"app_name": ""},
        "description": "Open empty app",
        "risk_level": "low"
    }
    actions = planner.plan(nlu_data)
    assert len(actions) == 1
    assert actions[0].action_type == "unhandled"
    assert actions[0].requires_permission is False


def test_parameter_validation_multi_step_invalid_step():
    planner = ActionPlanner()
    nlu_data = {
        "understood": True,
        "action": "multi_step",
        "parameters": {
            "steps": [
                {
                    "action": "volume_set",
                    "parameters": {"level": 200},  # Invalid
                    "description": "Volume 200"
                }
            ]
        }
    }
    actions = planner.plan(nlu_data)
    assert len(actions) == 1
    assert actions[0].action_type == "unhandled"
    assert actions[0].requires_permission is False


def test_describe_action_formats():
    from brain.planner import describe_action
    a1 = PlannedAction(action_type="run_command", parameters={"command": "dir C:\\Users"})
    assert describe_action(a1) == 'Run command: "dir C:\\Users"'

    a2 = PlannedAction(action_type="file_delete", parameters={"path": "C:\\temp\\file.txt"})
    assert describe_action(a2) == 'Delete file: "C:\\temp\\file.txt"'

    a3 = PlannedAction(action_type="file_create", parameters={"path": "notes.txt", "content": "hi"})
    assert describe_action(a3) == 'Create file: "notes.txt"'


def test_honest_confirmation_overrides_deceitful_llm_message():
    planner = ActionPlanner()
    # High risk action with deceitful LLM message
    nlu_data = {
        "understood": True,
        "action": "run_command",
        "parameters": {"command": "del important.txt"},
        "description": "Delete files",
        "risk_level": "high",
        "confirmation_message": "Just checking the weather forecast!"  # Deceitful
    }
    actions = planner.plan(nlu_data)
    assert len(actions) == 1
    assert actions[0].action_type == "run_command"
    assert actions[0].confirmation_message == 'Run command: "del important.txt"'
    assert "weather" not in actions[0].confirmation_message.lower()


