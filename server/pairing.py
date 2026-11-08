"""Persistent, revocable identities for ZENO remote-control devices."""

import hashlib
import json
import secrets
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from config import config


class DeviceRegistry:
    """Small local registry.  Only an authenticated pairing can create a device."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or (config.BASE_DIR / "paired_devices.json"))

    @contextmanager
    def _transaction(self, *, write=True):
        """Serialize the complete read/modify/replace operation across workers."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix(".lock").open("a+b") as lock:
            lock.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                devices = self._read()
                yield devices
                if write:
                    self._write(devices)
            finally:
                if os.name == "nt":
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock, fcntl.LOCK_UN)

    def _read(self) -> Dict[str, Dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not all(isinstance(record, dict) for record in data.values()):
                raise ValueError("Invalid paired-device registry.")
            return data
        except FileNotFoundError:
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
        with self._transaction() as devices:
            record = devices.get(device_id, {})
            if record.get("revoked") or not record.get("generation"):
                record["generation"] = secrets.token_hex(16)
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
            return record

    def is_active(self, device_id: str) -> bool:
        with self._transaction(write=False) as devices:
            record = devices.get(device_id)
            return bool(record and not record.get("revoked", False))

    def accepts_session(self, device_id: str, generation: str) -> bool:
        with self._transaction(write=False) as devices:
            record = devices.get(device_id)
            return bool(generation and record and not record.get("revoked") and record.get("generation") == generation)

    def touch(self, device_id: str, client_ip: str) -> None:
        with self._transaction() as devices:
            if device_id in devices:
                devices[device_id]["last_seen_at"] = datetime.now(timezone.utc).isoformat()
                devices[device_id]["last_ip"] = client_ip

    def list_safe(self) -> list[Dict[str, Any]]:
        with self._transaction(write=False) as devices:
            return [{"device_id": device_id, **{k: v for k, v in record.items() if k != "generation"}}
                    for device_id, record in devices.items()]

    def revoke(self, device_id: str) -> bool:
        with self._transaction() as devices:
            if device_id not in devices:
                return False
            devices[device_id]["revoked"] = True
            return True


device_registry = DeviceRegistry()
