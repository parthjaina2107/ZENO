"""
Permission System for Voice Agent
Safety gating ensuring no action runs without explicit user approval.
Supports local voice confirmation, console fallback, remote WebSocket approvals,
and structured audit trail logging.
"""

import asyncio
import datetime
import json
import logging
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from brain.planner import PlannedAction
from config import config

logger = logging.getLogger("VoiceAgent.Permissions")


class PermissionManager:
    def __init__(self, listener=None, speaker=None, audit_log_path: Optional[str] = None):
        self.listener = listener
        self.speaker = speaker
        self.audit_log_path = Path(audit_log_path or (config.BASE_DIR / "audit_log.jsonl"))
        self._pending_remote_requests: Dict[str, asyncio.Future] = {}

    def log_decision(
        self,
        action: PlannedAction,
        approved: bool,
        source: str = "local",
        reason: Optional[str] = None
    ):
        """Append permission decision to audit trail file."""
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "source": source,
            "action_type": action.action_type,
            "risk_level": action.risk_level,
            "description": action.description,
            "parameters": action.parameters,
            "approved": approved,
            "reason": reason or ("User approved" if approved else "User denied / timed out")
        }

        try:
            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to record audit log: {e}")

        logger.info(f"Audit: [{source.upper()}] Action '{action.action_type}' (Risk: {action.risk_level}) -> Approved: {approved}")

    async def request_permission_local(self, action: PlannedAction) -> bool:
        """
        Ask user locally via voice (speaker + listener) or console prompt.
        Always falls back to console input if voice confirmation is unclear/times out.
        """
        prompt_text = action.confirmation_message or f"Execute {action.description}?"
        risk = action.risk_level.lower()

        # Build prompt
        full_prompt = f"{prompt_text} Say YES to approve or NO to cancel."
        if risk == "high":
            full_prompt = f"Warning: High risk action! {prompt_text} Please confirm: Say YES to proceed or NO to abort."

        print(f"\n[Permission Required - {risk.upper()} RISK]: {full_prompt}")

        # Speak the prompt SYNCHRONOUSLY first so mic doesn't pick up the agent's own voice
        if self.speaker:
            self.speaker.speak_sync(full_prompt)

        # Small delay after speaking so mic doesn't catch echo
        import time
        time.sleep(0.3)

        # Try voice confirmation first
        approved = None
        if self.listener and self.listener.is_mic_available():
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(
                None,
                self.listener.listen_for_confirmation,
                config.CONFIRMATION_TIMEOUT
            )
            if res is True:
                approved = True
            elif res is False:
                approved = False
            # else: None = unclear/timeout, fall through to console

        # Always fall back to console input if voice was unclear or no mic
        if approved is None:
            print("  (Voice unclear or timed out. Type your answer below.)")
            loop = asyncio.get_running_loop()
            def ask_console():
                try:
                    ans = input(">>> Approve? (yes/no): ").strip().lower()
                    return ans in ("y", "yes", "approve", "ok", "sure", "do it", "go ahead")
                except (EOFError, KeyboardInterrupt):
                    return False
            approved = await loop.run_in_executor(None, ask_console)

        # Double confirmation for high-risk actions
        if approved and risk == "high":
            double_prompt = "Final confirmation required. This may be irreversible. Say YES or type yes to proceed."
            print(f"[Double Confirmation]: {double_prompt}")
            if self.speaker:
                self.speaker.speak_sync(double_prompt)

            time.sleep(0.3)

            double_approved = None
            if self.listener and self.listener.is_mic_available():
                loop = asyncio.get_running_loop()
                double_res = await loop.run_in_executor(
                    None,
                    self.listener.listen_for_confirmation,
                    10
                )
                if double_res is True:
                    double_approved = True
                elif double_res is False:
                    double_approved = False

            if double_approved is None:
                loop = asyncio.get_running_loop()
                def ask_double():
                    try:
                        ans = input(">>> Final confirm (yes/no): ").strip().lower()
                        return ans in ("yes", "y")
                    except (EOFError, KeyboardInterrupt):
                        return False
                double_approved = await loop.run_in_executor(None, ask_double)

            approved = double_approved

        self.log_decision(action, approved, source="local")
        return approved

    def create_remote_permission_request(self, action: PlannedAction) -> tuple[str, Dict[str, Any], asyncio.Future]:
        """Create a trackable remote permission request future."""
        request_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_remote_requests[request_id] = future

        payload = {
            "type": "permission_request",
            "request_id": request_id,
            "action_type": action.action_type,
            "description": action.description,
            "parameters": action.parameters,
            "risk_level": action.risk_level,
            "message": action.confirmation_message or f"Approve {action.description}?"
        }
        return request_id, payload, future

    def resolve_remote_permission(self, request_id: str, approved: bool) -> bool:
        """Called when a remote client sends permission_response."""
        future = self._pending_remote_requests.pop(request_id, None)
        if future and not future.done():
            future.set_result(approved)
            return True
        return False

    async def request_permission_remote(
        self,
        action: PlannedAction,
        send_func,
        timeout: Optional[int] = None
    ) -> bool:
        """
        Send permission request over WebSocket and await user's button tap.
        """
        timeout_seconds = timeout or config.REMOTE_CONFIRMATION_TIMEOUT
        request_id, payload, future = self.create_remote_permission_request(action)

        # Transmit request over WebSocket
        await send_func(payload)

        try:
            approved = await asyncio.wait_for(future, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            self._pending_remote_requests.pop(request_id, None)
            approved = False
            self.log_decision(action, False, source="remote", reason="Timeout waiting for remote approval")
            return False

        self.log_decision(action, approved, source="remote")
        return approved
