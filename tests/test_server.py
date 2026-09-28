"""
Unit tests for FastAPI endpoints and authentication.
"""

from fastapi.testclient import TestClient
from server.app import app
from server.auth import auth_manager

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "cpu_percent" in data


def test_auth_failure():
    response = client.post("/auth", data={"token": "wrong_password_xyz"})
    assert response.status_code == 401


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
