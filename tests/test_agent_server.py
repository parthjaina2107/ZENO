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
    from server.pairing import DeviceRegistry
    registry = DeviceRegistry(tmp_path / "devices.json")
    registry.pair("agent-test-device", "Test browser", "testclient")
    monkeypatch.setattr(server, "device_registry", registry)
    token = server.auth_manager.create_session_token("test-agent", device_id="agent-test-device")
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


def test_workspace_assets_and_browser_pairing(monkeypatch, tmp_path):
    server = importlib.import_module("server.app")
    from server.pairing import DeviceRegistry
    registry = DeviceRegistry(tmp_path / "devices.json")
    monkeypatch.setattr(server, "device_registry", registry)
    with TestClient(server.app) as client:
        for path in ("/", "/static/app.js", "/static/app.css", "/static/glass-loop.png", "/static/vendor/lucide.min.js"):
            assert client.get(path).status_code == 200
        response = client.post("/auth", data={"token": server.auth_manager.access_token,
                               "device_id": "workspace-browser", "device_label": "ZENO browser"})
        assert response.status_code == 200
        token = response.json()["jwt_token"]
        assert server.auth_manager.verify_session_token(token)["device_id"] == "workspace-browser"
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "auth", "token": token})
            assert ws.receive_json()["type"] == "auth_ok"
            ws.send_json({"type": "get_telemetry"})
            assert ws.receive_json()["type"] == "telemetry"
            registry.revoke("workspace-browser")
            ws.send_json({"type": "command", "text": "open notepad"})
            from starlette.websockets import WebSocketDisconnect
            with pytest.raises(WebSocketDisconnect) as error:
                ws.receive_json()
            assert error.value.code == 4003


def test_normal_command_signals_completion_after_all_results(remote):
    ws, executor, _ = remote
    ws.send_json({"type": "command", "text": "open notepad then type Hello", "mode": "command"})
    responses = []
    while True:
        event = ws.receive_json()
        if event["type"] == "command_finished":
            break
        if event["type"] == "response":
            responses.append(event)
    assert len(responses) == 2
    assert executor.execute.call_count == 2
