"""Persistent, revocable identities for ZENO remote-control devices."""

import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from config import config


class DeviceRegistry:
    """Small local registry.  Only an authenticated pairing can create a device."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or (config.BASE_DIR / "paired_devices.json"))

    def _read(self) -> Dict[str, Dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write(self, devices: Dict[str, Dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(devices, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.path)

    @staticmethod
    def fingerprint(device_id: str) -> str:
        return hashlib.sha256(device_id.encode("utf-8")).hexdigest()[:16]

    def pair(self, device_id: str, label: str, client_ip: str) -> Dict[str, Any]:
        if not device_id or len(device_id) > 128:
            raise ValueError("Invalid device identifier.")
        devices = self._read()
        record = devices.get(device_id, {})
        now = datetime.now(timezone.utc).isoformat()
        record.update({
            "label": (label or "Unnamed device")[:64],
            "fingerprint": self.fingerprint(device_id),
            "paired_at": record.get("paired_at", now),
            "last_seen_at": now,
            "last_ip": client_ip,
            "revoked": False,
        })
        devices[device_id] = record
        self._write(devices)
        return record

    def is_active(self, device_id: str) -> bool:
        return bool(device_id and (record := self._read().get(device_id)) and not record.get("revoked", False))

    def touch(self, device_id: str, client_ip: str) -> None:
        devices = self._read()
        if device_id in devices:
            devices[device_id]["last_seen_at"] = datetime.now(timezone.utc).isoformat()
            devices[device_id]["last_ip"] = client_ip
            self._write(devices)

    def list_safe(self) -> list[Dict[str, Any]]:
        return [dict(device_id=device_id, **record) for device_id, record in self._read().items()]

    def revoke(self, device_id: str) -> bool:
        devices = self._read()
        if device_id not in devices:
            return False
        devices[device_id]["revoked"] = True
        self._write(devices)
        return True


device_registry = DeviceRegistry()
