"""
Authentication and Session Manager for Voice Agent Remote Access.
Handles secret passphrase verification, JWT issuance and verification,
and brute-force rate-limiting protection.
"""

import time
import hashlib
import logging
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from config import config

logger = logging.getLogger("VoiceAgent.Auth")

MAX_FAILED_ATTEMPTS = 10
LOCKOUT_DURATION = 3600  # 1 hour in seconds


class AuthManager:
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or config.ACCESS_TOKEN
        self.secret_key = config.JWT_SECRET_KEY
        self.algorithm = config.JWT_ALGORITHM
        self.expiration_hours = config.JWT_EXPIRATION_HOURS

        # Rate limiting state: ip/identifier -> {"count": int, "lockout_until": float}
        self._attempts: Dict[str, Dict[str, Any]] = {}

    def is_locked_out(self, client_id: str) -> tuple[bool, int]:
        """Check if client is currently locked out. Returns (is_locked, seconds_left)."""
        now = time.time()
        record = self._attempts.get(client_id)
        if not record:
            return False, 0

        lockout_until = record.get("lockout_until", 0)
        if now < lockout_until:
            return True, int(lockout_until - now)
        return False, 0

    def record_attempt(self, client_id: str, success: bool):
        """Track authentication attempts to prevent brute force."""
        now = time.time()
        record = self._attempts.setdefault(client_id, {"count": 0, "lockout_until": 0})

        if success:
            # Reset on successful login
            self._attempts.pop(client_id, None)
            return

        record["count"] += 1
        logger.warning(f"Failed authentication attempt ({record['count']}/{MAX_FAILED_ATTEMPTS}) from {client_id}")

        if record["count"] >= MAX_FAILED_ATTEMPTS:
            record["lockout_until"] = now + LOCKOUT_DURATION
            logger.error(f"Client {client_id} locked out for 1 hour due to too many failed attempts.")

    def verify_passphrase(self, candidate: str, client_id: str = "default") -> bool:
        """Verify candidate token against configured ACCESS_TOKEN with constant-time compare."""
        locked, _ = self.is_locked_out(client_id)
        if locked:
            return False

        if not candidate:
            self.record_attempt(client_id, False)
            return False

        # Constant-time comparison
        valid = hashlib.sha256(candidate.strip().encode()).digest() == hashlib.sha256(self.access_token.encode()).digest()
        self.record_attempt(client_id, valid)
        return valid

    def create_session_token(self, client_id: str = "remote-user") -> str:
        """Create a 24-hour JWT session token."""
        now = int(time.time())
        expires = now + (self.expiration_hours * 3600)
        payload = {
            "sub": client_id,
            "iat": now,
            "exp": expires,
            "role": "controller"
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_session_token(self, token_str: str) -> Optional[Dict[str, Any]]:
        """Validate JWT signature and expiration. Returns payload if valid, None otherwise."""
        if not token_str:
            return None
        try:
            payload = jwt.decode(token_str, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            logger.debug(f"Invalid session token: {e}")
            return None


auth_manager = AuthManager()
