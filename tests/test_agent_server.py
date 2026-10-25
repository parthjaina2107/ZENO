"""Exercise the authenticated UI protocol through the real planning/runtime boundary."""
from unittest.mock import MagicMock
import importlib
import pytest
from fastapi.testclient import TestClient
from brain.zeno_brain import ZenoBrain
from brain.planner import ActionResult
from config import config
from executor.permissions import PermissionManager


@pytest.fixture
def remote(monkeypatch, tmp_path):
    server = importlib.import_module("server.app")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(config, "MEMORY_FILE", str(tmp_path / "memory.json"))
    executor = MagicMock()
    executor.execute.return_value = ActionResult(True, "Mock action executed", {"value": 50})
    brain = ZenoBrain(executor=executor)
    permissions = PermissionManager(audit_log_path=str(tmp_path / "audit.jsonl"))
    for name, value in {"task_executor": executor, "zeno_brain": brain, "action_planner": brain.planner,
                        "permission_manager": permissions, "host_speaker": MagicMock()}.items():
        monkeypatch.setattr(server, name, value)
    token = server.auth_manager.create_session_token("test-agent")
    with TestClient(server.app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "auth", "token": token})
            assert ws.receive_json()["type"] == "auth_ok"
            yield ws, executor, permissions


def until(ws, predicate):
    for _ in range(30):
        message = ws.receive_json()
        if predicate(message):
            return message
    raise AssertionError("Expected protocol event was not received")


def test_remote_agent_approves_phase_and_completes(remote):
    ws, executor, perms = remote
    ws.send_json({"type": "command", "text": "open notepad then type Hello ZENO", "mode": "agent"})
    request = until(ws, lambda m: m["type"] == "permission_request")
    assert request["action_type"] == "task_plan"
    assert "Hello ZENO" in request["message"]
    executor.execute.assert_not_called()
    ws.send_json({"type": "permission_response", "request_id": request["request_id"],
                  "action_id": request["action_id"], "approved": True})
    final = until(ws, lambda m: m.get("status") == "completed")
    assert final["completed"] == 2
    assert executor.execute.call_count == 2
    assert not perms._pending_remote_requests


def test_spoken_stop_interrupts_permission_wait(remote):
    ws, executor, perms = remote
    ws.send_json({"type": "command", "text": "task: type Hello"})
    until(ws, lambda m: m["type"] == "permission_request")
    ws.send_json({"type": "command", "text": "Hey ZENO, stop"})
    until(ws, lambda m: m.get("kind") == "abort")
    until(ws, lambda m: m.get("status") == "cancelled")
    executor.execute.assert_not_called()
    assert not perms._pending_remote_requests


def test_string_false_is_not_approval(remote):
    ws, executor, perms = remote
    ws.send_json({"type": "command", "text": "task: type Hello"})
    request = until(ws, lambda m: m["type"] == "permission_request")
    ws.send_json({"type": "permission_response", "request_id": request["request_id"],
                  "action_id": request["action_id"], "approved": "false"})
    until(ws, lambda m: m.get("status") == "cancelled")
    executor.execute.assert_not_called()


def test_remote_high_risk_still_requires_two_approvals(remote):
    ws, executor, perms = remote
    ws.send_json({"type": "command", "text": "task: run command whoami"})
    request = until(ws, lambda m: m["type"] == "permission_request")
    ws.send_json({"type": "permission_response", "request_id": request["request_id"],
                  "action_id": request["action_id"], "approved": True})
    final_request = until(ws, lambda m: m["type"] == "permission_request")
    assert "Final confirmation" in final_request["message"]
    executor.execute.assert_not_called()
    ws.send_json({"type": "permission_response", "request_id": final_request["request_id"],
                  "action_id": final_request["action_id"], "approved": False})
    until(ws, lambda m: m.get("status") == "cancelled")
    executor.execute.assert_not_called()
