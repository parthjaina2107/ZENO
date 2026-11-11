"""
Unit tests for FastAPI endpoints and authentication.
"""

from fastapi.testclient import TestClient
from server.app import app
from server.auth import auth_manager

import pytest

pytestmark = pytest.mark.usefixtures("browser_grant")
from server.pairing import DeviceRegistry

client = TestClient(app, base_url="http://localhost", client=("127.0.0.1", 50000))


@pytest.fixture(autouse=True)
def isolate_devices(tmp_path, monkeypatch):
    from importlib import import_module
    monkeypatch.setattr(import_module("server.app"), "device_registry", DeviceRegistry(tmp_path / "devices.json"))
    from config import config
    monkeypatch.setattr(config, "BASE_DIR", tmp_path)
    monkeypatch.setattr(config, "MEMORY_FILE", str(tmp_path / "memory.json"))
    monkeypatch.setattr(auth_manager, "_attempts", {})


def test_health_endpoint():
    # Health endpoint is protected by JWT
    unauth_resp = client.get("/health")
    assert unauth_resp.status_code == 401

    # With valid JWT
    valid_pass = auth_manager.access_token
    auth_resp = client.post("/auth", data={"pairing_code": "test-code", "token": valid_pass})
    jwt_token = auth_resp.json()["jwt_token"]

    auth_health = client.get("/health", headers={"Authorization": f"Bearer {jwt_token}"})
    assert auth_health.status_code == 200
    data = auth_health.json()
    assert data["status"] == "healthy"
    assert "cpu_percent" in data


def test_auth_failure():
    response = client.post("/auth", data={"pairing_code": "test-code", "token": "wrong_password_xyz"})
    assert response.status_code == 401


def test_auth_lockout_keyed_by_client_ip():
    # Reset attempts for testing
    auth_manager._attempts.clear()

    # 10 failed attempts from IP 198.51.100.1 via proxy header
    headers_ip1 = {"X-Forwarded-For": "198.51.100.1"}
    for _ in range(10):
        resp = client.post("/auth", data={"pairing_code": "test-code", "token": "bad_password"}, headers=headers_ip1)

    # 11th attempt from IP 1 is locked out (429)
    resp_locked = client.post("/auth", data={"pairing_code": "test-code", "token": "bad_password"}, headers=headers_ip1)
    assert resp_locked.status_code == 429
    assert "Locked out" in resp_locked.json()["detail"]

    # Attempt from IP 2 (198.51.100.2) is NOT locked out (returns 401, not 429)
    headers_ip2 = {"X-Forwarded-For": "198.51.100.2"}
    resp_ip2 = client.post("/auth", data={"pairing_code": "test-code", "token": "bad_password"}, headers=headers_ip2)
    assert resp_ip2.status_code == 401


def test_auth_success():
    valid_token = auth_manager.access_token
    response = client.post("/auth", data={"pairing_code": "test-code", "token": valid_token})
    assert response.status_code == 200
    data = response.json()
    assert "jwt_token" in data
    token = data["jwt_token"]

    # Verify token
    payload = auth_manager.verify_session_token(token)
    assert payload is not None
    assert payload.get("role") == "controller"



def test_home_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "ZENO" in response.text


def test_shared_subsystems():
    from server.app import init_shared_subsystems, get_subsystems
    from unittest.mock import MagicMock

    dummy_exec = MagicMock()
    dummy_brain = MagicMock()
    dummy_perms = MagicMock()
    dummy_speaker = MagicMock()

    init_shared_subsystems(
        executor=dummy_exec,
        brain=dummy_brain,
        permissions=dummy_perms,
        speaker=dummy_speaker
    )

    t_exec, t_plan, t_brain, t_perms, t_speaker = get_subsystems()
    assert t_exec is dummy_exec
    assert t_brain is dummy_brain
    assert t_perms is dummy_perms
    assert t_speaker is dummy_speaker


def test_websocket_command_approval_no_deadlock():
    from unittest.mock import MagicMock
    from server.app import init_shared_subsystems
    from executor.task_executor import ActionResult

    valid_token = auth_manager.access_token
    auth_resp = client.post("/auth", data={"pairing_code": "test-code", "token": valid_token})
    jwt_token = auth_resp.json()["jwt_token"]

    # Mock executor to succeed quickly without actually opening notepad
    mock_exec = MagicMock()
    mock_exec.execute.return_value = ActionResult(True, "Shutdown requested")
    from brain import ZenoBrain
    from executor.permissions import PermissionManager
    from voice.speaker import VoiceSpeaker
    mock_brain = ZenoBrain(executor=mock_exec)
    mock_perms = PermissionManager()
    mock_speaker = MagicMock()

    init_shared_subsystems(
        executor=mock_exec,
        brain=mock_brain,
        permissions=mock_perms,
        speaker=mock_speaker
    )

    with client.websocket_connect("ws://localhost/ws") as ws:
        ws.send_json({"type": "auth", "token": jwt_token})
        assert ws.receive_json()["type"] == "auth_ok"
        # Send command that requires permission
        ws.send_json({"type": "command", "text": "shutdown"})

        # First message should be permission request
        msg1 = ws.receive_json()
        assert msg1.get("type") == "permission_request"
        req_id = msg1.get("request_id")
        assert req_id is not None

        # Client sends approval
        ws.send_json({"type": "permission_response", "request_id": req_id, "action_id": msg1["action_id"], "approved": True})

        # Server must process approval and send success response without deadlocking
        msg2 = ws.receive_json()
        assert msg2.get("type") == "permission_request"
        assert "Final confirmation" in msg2["message"]
        mock_exec.execute.assert_not_called()
        ws.send_json({"type": "permission_response", "request_id": msg2["request_id"], "action_id": msg2["action_id"], "approved": True})
        msg2 = ws.receive_json()
        assert msg2.get("type") == "response"
        assert "shutdown" in msg2.get("message", "").lower()


def test_websocket_first_message_auth():
    valid_token = auth_manager.access_token
    auth_resp = client.post("/auth", data={"pairing_code": "test-code", "token": valid_token})
    jwt_token = auth_resp.json()["jwt_token"]

    # Connect to /ws without token in URL
    with client.websocket_connect("ws://localhost/ws") as ws:
        # Send JWT as first message
        ws.send_json({"type": "auth", "token": jwt_token})
        ack = ws.receive_json()
        assert ack.get("type") == "auth_ok"


def test_websocket_abort_kill_switch():
    valid_token = auth_manager.access_token
    auth_resp = client.post("/auth", data={"pairing_code": "test-code", "token": valid_token})
    jwt_token = auth_resp.json()["jwt_token"]

    with client.websocket_connect("ws://localhost/ws") as ws:
        ws.send_json({"type": "auth", "token": jwt_token})
        ack = ws.receive_json()
        assert ack.get("type") == "auth_ok"

        # Send abort signal
        ws.send_json({"type": "abort"})
        resp = ws.receive_json()
        assert resp.get("type") == "response"
        assert "aborted" in resp.get("message", "").lower()


def test_remote_routine_multistep_executes_without_permission_prompts():
    from unittest.mock import MagicMock, AsyncMock
    from brain.planner import ActionPlanner, ActionResult
    from brain.zeno_brain import BrainResponse
    from server.app import init_shared_subsystems

    executor = MagicMock()
    executor.execute.return_value = ActionResult(True, "Routine action completed")
    planner = ActionPlanner(executor=executor)
    actions = planner.plan({"understood": True, "action": "multi_step", "parameters": {"steps": [
        {"action": "open_app", "parameters": {"app_name": "spotify"}},
        {"action": "volume_set", "parameters": {"level": 30}},
    ]}})
    brain = MagicMock()
    brain.think = AsyncMock(return_value=BrainResponse("action", "", actions))
    permissions = MagicMock()
    init_shared_subsystems(executor=executor, brain=brain, planner=planner,
                           permissions=permissions, speaker=MagicMock())
    auth_manager._attempts.clear()
    token = client.post("/auth", data={"pairing_code": "test-code", "token": auth_manager.access_token}).json()["jwt_token"]
    with client.websocket_connect("ws://localhost/ws") as ws:
        ws.send_json({"type": "auth", "token": token})
        assert ws.receive_json()["type"] == "auth_ok"
        ws.send_json({"type": "command", "text": "open spotify and set volume to 30"})
        assert ws.receive_json()["type"] == "response"
        assert ws.receive_json()["type"] == "response"
    assert executor.execute.call_count == 2
    permissions.request_permission_remote.assert_not_called()
    permissions.request_plan_review_remote.assert_not_called()


def test_proxy_headers_from_a_direct_peer_cannot_rotate_lockout_identity():
    direct = TestClient(app, base_url="http://localhost", client=("192.0.2.123", 50000))
    for i in range(11):
        result = direct.post("/auth", data={"pairing_code": "test-code", "token": "invalid"}, headers={
            "X-Forwarded-For": f"198.51.100.{i}", "X-Forwarded-Proto": "https"})
    assert result.status_code == 429


def test_expired_lockout_gives_a_fresh_attempt_window():
    import time
    auth_manager._attempts["test-peer"] = {"count": 10, "lockout_until": time.time() - 1}
    assert not auth_manager.verify_passphrase("bad", "test-peer")
    assert auth_manager._attempts["test-peer"]["count"] == 1
    assert not auth_manager.is_locked_out("test-peer")[0]


def test_repair_cannot_revive_prior_token_and_audit_skips_damaged_rows(tmp_path, monkeypatch):
    from importlib import import_module
    from config import config
    server = import_module("server.app")
    monkeypatch.setattr(config, "BASE_DIR", tmp_path)
    data = {"pairing_code": "test-code", "token": auth_manager.access_token, "device_id": "repeat"}
    old = client.post("/auth", data=data).json()["jwt_token"]
    assert server.device_registry.revoke("repeat")
    server.remote_grant.code = "test-code"
    new = client.post("/auth", data=data).json()["jwt_token"]
    for endpoint in ["/health", "/api/devices", "/api/audit"]:
        assert client.get(endpoint, headers={"Authorization": "Bearer " + old}).status_code == 401
    path = tmp_path / "audit_log.jsonl"
    path.write_bytes(b"x" * (5 * 1024 * 1024) + b'\n{"event":"a"}\nbroken\n[]\n{"event":"b"}\n')
    result = client.get("/api/audit", headers={"Authorization": "Bearer " + new}).json()
    assert result == {"events": [{"event": "a"}, {"event": "b"}], "skipped": 2, "truncated": True}


def test_idle_socket_expires_after_authentication(monkeypatch):
    import time
    import jwt
    from starlette.websockets import WebSocketDisconnect
    import importlib
    server = importlib.import_module("server.app")
    record = server.device_registry.pair("short", "short", "test")
    expires = time.time() + 1.5
    token = jwt.encode({"grant_id": server.remote_grant.id, "sub": "test", "device_id": "short", "generation": record["generation"], "exp": expires},
                       auth_manager.secret_key, algorithm=auth_manager.algorithm)
    with client.websocket_connect("ws://localhost/ws") as ws:
        ws.send_json({"type": "auth", "token": token})
        assert ws.receive_json()["type"] == "auth_ok"
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 4001


def test_registry_keeps_concurrent_worker_changes(tmp_path):
    import subprocess
    import sys
    path = tmp_path / "devices.json"
    registry = DeviceRegistry(path)
    registry.pair("revoked", "existing", "local")
    code = """
import importlib.util
import sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("pairing_worker", "server/pairing.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
registry = module.DeviceRegistry(Path(sys.argv[1]))
for i in range(12):
    registry.pair(sys.argv[2] + str(i), "worker", "localhost")
    registry.touch("revoked", "localhost")
"""
    workers = [subprocess.Popen([sys.executable, "-c", code, str(path), prefix]) for prefix in ["a", "b", "c"]]
    try:
        assert registry.revoke("revoked")
        for worker in workers:
            assert worker.wait(timeout=30) == 0
    finally:
        for worker in workers:
            if worker.poll() is None:
                worker.kill()
                worker.wait()
    assert len(registry.list_safe()) == 37
    assert not registry.is_active("revoked")

def test_pairing_needs_fresh_code_and_pc_consent(browser_grant, monkeypatch):
    import importlib
    server = importlib.import_module("server.app")
    data = {"token": auth_manager.access_token, "device_id": "new-phone"}
    assert client.post("/auth", data=data).status_code == 403
    data["pairing_code"] = browser_grant.code
    monkeypatch.setattr(server, "owner_approves", lambda _: False)
    assert client.post("/auth", data=data).status_code == 403
    monkeypatch.setattr(server, "owner_approves", lambda _: True)
    assert client.post("/auth", data=data).status_code == 403
    assert not server.device_registry.list_safe()


def test_browser_origin_and_url_credentials(browser_grant):
    from starlette.websockets import WebSocketDisconnect
    data = {"token": auth_manager.access_token, "pairing_code": browser_grant.code}
    assert client.post("/auth", data=data, headers={"Origin": "https://elsewhere.invalid"}).status_code == 403
    token = client.post("/auth", data=data, headers={"Origin": "http://localhost"}).json()["jwt_token"]
    assert client.get("/health", params={"token": token}).status_code == 401
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("ws://localhost/ws?token=" + token):
        pass
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("ws://localhost/ws", headers={"Origin": "null"}):
        pass


def test_media_scope_and_lock_enforced(browser_grant, monkeypatch):
    import importlib
    from unittest.mock import MagicMock
    from starlette.websockets import WebSocketDisconnect
    server = importlib.import_module("server.app")
    browser_grant.scope = "media"
    executor, brain = MagicMock(), MagicMock()
    monkeypatch.setattr(server, "get_subsystems", lambda: (executor, None, brain, MagicMock(), MagicMock()))
    token = client.post("/auth", data={"token": auth_manager.access_token, "pairing_code": browser_grant.code}).json()["jwt_token"]
    headers = {"Authorization": "Bearer " + token}
    assert client.get("/api/audit", headers=headers).status_code == 403
    assert client.get("/api/devices", headers=headers).status_code == 403
    with client.websocket_connect("ws://localhost/ws") as ws:
        ws.send_json({"type": "auth", "token": token})
        assert ws.receive_json()["scope"] == "media"
        ws.send_json({"type": "command", "text": "read my email", "mode": "agent"})
        assert ws.receive_json()["type"] == "response"
        assert ws.receive_json()["status"] == "blocked"
        brain.think.assert_not_called()
        executor.execute.assert_not_called()
        executor.execute.return_value.message = "Paused"
        ws.send_json({"type": "command", "text": "pause"})
        assert ws.receive_json()["message"] == "Paused"
        assert ws.receive_json()["status"] == "completed"
        assert executor.execute.call_args.args[0].parameters == {"command": "pause"}
        monkeypatch.setattr("server.remote_access.desktop_unlocked", lambda: False)
        ws.send_json({"type": "get_telemetry"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
    monkeypatch.setattr("server.remote_access.desktop_unlocked", lambda: True)
    assert client.get("/health", headers=headers).status_code == 401


def test_idle_grant_expires(browser_grant):
    browser_grant.last_activity -= 301
    assert not browser_grant.active()
    assert not browser_grant.consume("test-code")

def test_server_launcher_is_local_and_stops_on_grant_end(monkeypatch):
    import importlib
    import time
    import httpx
    import main
    from unittest.mock import MagicMock
    server = importlib.import_module("server.app")
    monkeypatch.setattr(server, "init_shared_subsystems", MagicMock())
    monkeypatch.setattr(server, "remote_grant", None)
    host = main.VoiceAgentApp.__new__(main.VoiceAgentApp)
    host.port = 0
    host.enable_tunnel = False
    host.remote_scope = "media"
    host.tunnel_manager = MagicMock()
    host.executor = host.brain = host.permissions = host.speaker = host.planner = MagicMock()
    host.start_web_server()
    try:
        with httpx.Client(trust_env=False) as local:
            for _ in range(50):
                try:
                    response = local.get(f"http://127.0.0.1:{host.port}/", timeout=1)
                    break
                except httpx.ConnectError:
                    time.sleep(0.05)
            else:
                pytest.fail("Loopback server did not start")
            assert response.status_code == 200
        host.tunnel_manager.start_tunnel.assert_not_called()
    finally:
        server.remote_grant.started -= 901
        host.server_thread.join(5)
    assert not host.server_thread.is_alive()
