"""
Unit tests for PermissionManager.
"""

import pytest
from brain.planner import PlannedAction
from executor.permissions import PermissionManager


def test_permission_audit_log(tmp_path):
    audit_file = tmp_path / "test_audit.jsonl"
    pm = PermissionManager(audit_log_path=str(audit_file))

    action = PlannedAction(
        action_type="open_app",
        parameters={"app_name": "notepad"},
        description="Open Notepad",
        risk_level="low"
    )

    pm.log_decision(action, approved=True, source="test")
    assert audit_file.exists()
    content = audit_file.read_text(encoding="utf-8")
    assert "open_app" in content
    assert '"approved": true' in content


@pytest.mark.asyncio
async def test_remote_permission_resolution():
    pm = PermissionManager()
    action = PlannedAction(
        action_type="run_command",
        parameters={"command": "dir"},
        description="List files",
        risk_level="medium"
    )

    sent_payloads = []

    async def mock_send(payload):
        sent_payloads.append(payload)

    # Launch permission request in task
    import asyncio
    req_task = asyncio.create_task(pm.request_permission_remote(action, mock_send, timeout=5))
    
    # Give time for future creation
    await asyncio.sleep(0.05)
    assert len(sent_payloads) == 1
    assert sent_payloads[0]["message"] == 'Run command: "dir"'
    req_id = sent_payloads[0]["request_id"]

    # Client approves
    resolved = pm.resolve_remote_permission(req_id, True)
    assert resolved is True

    result = await req_task
    assert result is True


def test_action_id_hash_deterministic():
    a1 = PlannedAction(action_type="run_command", parameters={"command": "dir"})
    a2 = PlannedAction(action_type="run_command", parameters={"command": "dir"})
    a3 = PlannedAction(action_type="run_command", parameters={"command": "whoami"})

    assert hasattr(a1, "action_id")
    assert a1.action_id
    assert a1.action_id == a2.action_id
    assert a1.action_id != a3.action_id


@pytest.mark.asyncio
async def test_remote_permission_binding_mismatch_rejected():
    pm = PermissionManager()
    action = PlannedAction(
        action_type="run_command",
        parameters={"command": "dir"},
        description="List files",
        risk_level="high"
    )

    sent_payloads = []
    async def mock_send(payload):
        sent_payloads.append(payload)

    import asyncio
    req_task = asyncio.create_task(pm.request_permission_remote(action, mock_send, timeout=5))
    await asyncio.sleep(0.05)

    assert len(sent_payloads) == 1
    assert "action_id" in sent_payloads[0]
    assert sent_payloads[0]["action_id"] == action.action_id
    req_id = sent_payloads[0]["request_id"]

    # Attempt to approve with mismatched action_id
    resolved = pm.resolve_remote_permission(req_id, approved=True, action_id="wrong_tampered_action_id")
    assert resolved is False

    result = await req_task
    assert result is False

