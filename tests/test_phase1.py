import asyncio

import pytest

from brain.planner import PlannedAction
from executor.permissions import PermissionManager
from server.pairing import DeviceRegistry


def test_device_registry_pairs_and_revokes(tmp_path):
    registry = DeviceRegistry(tmp_path / "devices.json")
    record = registry.pair("phone-a", "Test phone", "127.0.0.1")
    assert record["revoked"] is False
    assert registry.is_active("phone-a") is True
    assert registry.revoke("phone-a") is True
    assert registry.is_active("phone-a") is False


@pytest.mark.asyncio
async def test_plan_review_is_bound_to_device_and_action_list():
    manager = PermissionManager()
    actions = [
        PlannedAction("open_app", {"app_name": "notepad"}),
        PlannedAction("volume_set", {"level": 25}),
    ]
    sent = []

    async def send(payload):
        sent.append(payload)

    task = asyncio.create_task(manager.request_plan_review_remote(actions, send, device_id="phone-a", timeout=2))
    await asyncio.sleep(0.02)
    request = sent[0]
    action_ids = [step["action_id"] for step in request["steps"]]
    assert manager.resolve_plan_review(request["request_id"], True, action_ids, "other-phone") is False
    assert manager.resolve_plan_review(request["request_id"], True, action_ids, "phone-a") is True
    assert await task is True
