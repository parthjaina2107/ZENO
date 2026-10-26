import pytest
from brain.planner import ActionPlanner


@pytest.mark.parametrize("action,parameters,required", [
    ("open_app", {"app_name": "spotify"}, False),
    ("close_app", {"process_name": "spotify.exe"}, False),
    ("open_url", {"url": "https://example.com"}, False),
    ("volume_set", {"level": 40}, False),
    ("type_text", {"text": "hello"}, False),
    ("keyboard_shortcut", {"keys": ["ctrl", "s"]}, False),
    ("mouse_click", {"x": 10, "y": 20}, False),
    ("file_create", {"path": "Documents/notes.txt"}, False),
    ("file_move", {"source": "Documents/a.txt", "destination": "Documents/b.txt"}, False),
    ("file_copy", {"source": "Documents/a.txt", "destination": "Documents/b.txt"}, False),
    ("run_command", {"command": "whoami"}, False),
    ("file_delete", {"path": "Documents/notes.txt"}, True),
    ("shutdown", {"mode": "shutdown"}, True),
    ("shutdown", {"mode": "restart"}, True),
    ("shutdown", {"mode": "sleep"}, False),
    ("shutdown", {"mode": "lock"}, False),
])
def test_permission_policy_for_single_and_multistep_actions(action, parameters, required):
    planner = ActionPlanner()
    # Even an LLM high-risk label must not reintroduce routine approvals.
    step = {"action": action, "parameters": parameters, "risk_level": "high"}
    single = planner.plan({"understood": True, **step})
    multiple = planner.plan({"understood": True, "action": "multi_step", "parameters": {"steps": [step]}})
    assert single[0].requires_permission is required
    assert multiple[0].requires_permission is required
