"""Exercise the authenticated UI protocol through the real planning/runtime boundary."""
from unittest.mock import MagicMock
import importlib
import pytest

pytestmark = pytest.mark.usefixtures("browser_grant")
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
    device = registry.pair("agent-test-device", "Test browser", "testclient")
    monkeypatch.setattr(server, "device_registry", registry)
    token = server.auth_manager.create_session_token("test-agent", device_id="agent-test-device", generation=device["generation"], grant_id=server.remote_grant.id)
    with TestClient(server.app, base_url="http://localhost") as client:
        with client.websocket_connect("ws://localhost/ws") as ws:
            ws.send_json({"type": "auth", "token": token})
            assert ws.receive_json()["type"] == "auth_ok"
            yield ws, executor, permissions


def until(ws, predicate):
    for _ in range(30):
        message = ws.receive_json()
        if predicate(message):
            return message
    raise AssertionError("Expected protocol event was not received")


def test_remote_just_talk_never_executes_unprefixed_action(remote):
    ws, executor, perms = remote
    ws.send_json({'type': 'command', 'text': 'open notepad then type Hello', 'mode': 'chat'})
    final = until(ws, lambda message: message.get('type') == 'response')
    assert final['kind'] == 'chat'
    until(ws, lambda message: message.get('type') == 'command_finished')
    executor.execute.assert_not_called()
    assert not perms._pending_remote_requests


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
    with TestClient(server.app, base_url="http://localhost") as client:
        for path in ("/", "/static/app.js", "/static/app.css", "/static/liquid-glass.css", "/static/glass-loop.png", "/static/vendor/lucide.min.js"):
            assert client.get(path).status_code == 200
        response = client.post("/auth", data={"pairing_code": "test-code", "token": server.auth_manager.access_token,
                               "device_id": "workspace-browser", "device_label": "ZENO browser"})
        assert response.status_code == 200
        token = response.json()["jwt_token"]
        assert server.auth_manager.verify_session_token(token)["device_id"] == "workspace-browser"
        with client.websocket_connect("ws://localhost/ws") as ws:
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


def test_two_remote_clients_finish_their_own_folder_requests(tmp_path, monkeypatch):
    from executor.task_executor import TaskExecutor
    from executor.file_ops import FileOps
    from server.pairing import DeviceRegistry
    server = importlib.import_module("server.app")
    monkeypatch.setattr(config, "MEMORY_FILE", str(tmp_path / "memory.json"))
    monkeypatch.setattr("executor.file_ops.user_folder", lambda name: tmp_path / name)
    executor = TaskExecutor()
    executor.file = FileOps([str(tmp_path)])
    brain = ZenoBrain(executor=executor)
    registry = DeviceRegistry(tmp_path / "devices.json")
    permissions = PermissionManager(audit_log_path=str(tmp_path / "audit.jsonl"))
    for name, obj in dict(task_executor=executor, action_planner=brain.planner, zeno_brain=brain,
                          permission_manager=permissions, host_speaker=MagicMock(), device_registry=registry).items():
        monkeypatch.setattr(server, name, obj)

    def command(socket, text):
        socket.send_json({"type": "command", "text": text})
        response = until(socket, lambda m: m.get("type") == "response")
        until(socket, lambda m: m.get("type") == "command_finished")
        return response["message"]

    with TestClient(server.app, base_url="http://localhost") as client, client.websocket_connect("ws://localhost/ws") as a, client.websocket_connect("ws://localhost/ws") as b:
        for socket, name in [(a, "first"), (b, "second")]:
            server.remote_grant.code = "test-code"
            token = client.post("/auth", data={"pairing_code": "test-code", "token": server.auth_manager.access_token, "device_id": name}).json()["jwt_token"]
            socket.send_json({"type": "auth", "token": token})
            assert socket.receive_json()["type"] == "auth_ok"
        assert "name" in command(a, "create a folder on desktop")
        assert "name" in command(b, "create a folder in documents")
        assert "Created" in command(a, "call it Alpha")
        assert "Created" in command(b, "call it Beta")
        assert (tmp_path / "desktop" / "Alpha").is_dir()
        assert (tmp_path / "documents" / "Beta").is_dir()
        assert "MiXeD ZENO" in command(a, 'run command echo "MiXeD ZENO"')
        assert "unsupported" in command(b, "run command echo ok & whoami")
        assert not brain.memory.short_term_history


def test_explicit_agent_folder_still_requires_plan_approval(remote):
    ws, executor, _ = remote
    ws.send_json({"type": "command", "text": "task: create folder Demo on desktop"})
    request = until(ws, lambda m: m["type"] == "permission_request")
    assert request["action_type"] == "task_plan"
    executor.execute.assert_not_called()
    ws.send_json({"type": "permission_response", "request_id": request["request_id"],
                  "action_id": request["action_id"], "approved": False})
    until(ws, lambda m: m.get("status") == "cancelled")
    executor.execute.assert_not_called()


def test_folder_clarification_preserves_original_approval_mode(remote):
    ws, executor, _ = remote
    ws.send_json({"type": "command", "text": "task: create a folder on desktop"})
    until(ws, lambda m: "What should I name" in m.get("message", ""))
    until(ws, lambda m: m["type"] == "command_finished")
    ws.send_json({"type": "command", "text": "call it One Two"})
    request = until(ws, lambda m: m["type"] == "permission_request")
    assert request["action_type"] == "task_plan"
    executor.execute.assert_not_called()
    ws.send_json({"type": "permission_response", "request_id": request["request_id"], "approved": True})
    until(ws, lambda m: m.get("status") == "cancelled")
    executor.execute.assert_not_called()


def test_busy_and_oversized_commands_return_terminal_feedback(remote):
    from executor.agent_runner import TaskRun, coordinator
    ws, _, _ = remote
    ws.send_json({"type": "command", "text": "x" * 12001})
    assert ws.receive_json()["type"] == "error"
    owner = TaskRun("other command", "other connection")
    assert coordinator.begin(owner)
    try:
        ws.send_json({"type": "command", "text": "check battery"})
        assert "busy" in ws.receive_json()["message"]
        assert ws.receive_json() == {"type": "command_finished", "status": "blocked"}
    finally:
        coordinator.finish(owner)


def test_single_command_exposes_failed_result(remote):
    ws, executor, _ = remote
    executor.execute.return_value = ActionResult(False, "Synthetic failure")
    ws.send_json({"type": "command", "text": "check battery", "mode": "command"})
    assert until(ws, lambda m: m["type"] == "command_finished")["status"] == "failed"
