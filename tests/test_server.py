"""
Unit tests for FastAPI endpoints and authentication.
"""

from fastapi.testclient import TestClient
from server.app import app
from server.auth import auth_manager

client = TestClient(app)


def test_health_endpoint():
    # Health endpoint is protected by JWT
    unauth_resp = client.get("/health")
    assert unauth_resp.status_code == 401

    # With valid JWT
    valid_pass = auth_manager.access_token
    auth_resp = client.post("/auth", data={"token": valid_pass})
    jwt_token = auth_resp.json()["jwt_token"]

    auth_health = client.get("/health", headers={"Authorization": f"Bearer {jwt_token}"})
    assert auth_health.status_code == 200
    data = auth_health.json()
    assert data["status"] == "healthy"
    assert "cpu_percent" in data


def test_auth_failure():
    response = client.post("/auth", data={"token": "wrong_password_xyz"})
    assert response.status_code == 401


def test_auth_lockout_keyed_by_client_ip():
    # Reset attempts for testing
    auth_manager._attempts.clear()

    # 10 failed attempts from IP 198.51.100.1 via proxy header
    headers_ip1 = {"X-Forwarded-For": "198.51.100.1"}
    for _ in range(10):
        resp = client.post("/auth", data={"token": "bad_password"}, headers=headers_ip1)

    # 11th attempt from IP 1 is locked out (429)
    resp_locked = client.post("/auth", data={"token": "bad_password"}, headers=headers_ip1)
    assert resp_locked.status_code == 429
    assert "Locked out" in resp_locked.json()["detail"]

    # Attempt from IP 2 (198.51.100.2) is NOT locked out (returns 401, not 429)
    headers_ip2 = {"X-Forwarded-For": "198.51.100.2"}
    resp_ip2 = client.post("/auth", data={"token": "bad_password"}, headers=headers_ip2)
    assert resp_ip2.status_code == 401


def test_auth_success():
    valid_token = auth_manager.access_token
    response = client.post("/auth", data={"token": valid_token})
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
    auth_resp = client.post("/auth", data={"token": valid_token})
    jwt_token = auth_resp.json()["jwt_token"]

    # Mock executor to succeed quickly without actually opening notepad
    mock_exec = MagicMock()
    mock_exec.execute.return_value = ActionResult(True, "Opened notepad", {"pid": 1234})
    from brain import ZenoBrain
    from executor.permissions import PermissionManager
    from voice.speaker import VoiceSpeaker
    mock_brain = ZenoBrain(executor=mock_exec)
    mock_perms = PermissionManager()
    mock_speaker = VoiceSpeaker()

    init_shared_subsystems(
        executor=mock_exec,
        brain=mock_brain,
        permissions=mock_perms,
        speaker=mock_speaker
    )

    with client.websocket_connect(f"/ws?token={jwt_token}") as ws:
        # Send command that requires permission
        ws.send_json({"type": "command", "text": "open notepad"})

        # First message should be permission request
        msg1 = ws.receive_json()
        assert msg1.get("type") == "permission_request"
        req_id = msg1.get("request_id")
        assert req_id is not None

        # Client sends approval
        ws.send_json({"type": "permission_response", "request_id": req_id, "approved": True})

        # Server must process approval and send success response without deadlocking
        msg2 = ws.receive_json()
        assert msg2.get("type") == "response"
        assert "notepad" in msg2.get("message", "").lower()


def test_websocket_first_message_auth():
    valid_token = auth_manager.access_token
    auth_resp = client.post("/auth", data={"token": valid_token})
    jwt_token = auth_resp.json()["jwt_token"]

    # Connect to /ws without token in URL
    with client.websocket_connect("/ws") as ws:
        # Send JWT as first message
        ws.send_json({"type": "auth", "token": jwt_token})
        ack = ws.receive_json()
        assert ack.get("type") == "auth_ok"

