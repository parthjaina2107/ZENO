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
from brain.planner import PlannedAction, describe_action
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
            "event": "permission_decision",
            "action_id": getattr(action, "action_id", None),
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

    def log_result(
        self,
        action: PlannedAction,
        result: Any,
        source: str = "local"
    ):
        """Append action execution result to audit trail file next to its approval."""
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "event": "execution_result",
            "action_id": getattr(action, "action_id", None),
            "source": source,
            "action_type": action.action_type,
            "success": getattr(result, "success", False),
            "message": getattr(result, "message", ""),
            "error": getattr(result, "error", None)
        }

        try:
            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to record audit log result: {e}")

        logger.info(f"Audit Result: [{source.upper()}] Action '{action.action_type}' -> Success: {getattr(result, 'success', False)}")

    async def request_permission_local(self, action: PlannedAction) -> bool:
        """
        Ask user locally via voice (speaker + listener) or console prompt.
        Always falls back to console input if voice confirmation is unclear/times out.
        """
        risk = action.risk_level.lower()
        if risk in ("medium", "high"):
            prompt_text = describe_action(action)
        else:
            prompt_text = action.confirmation_message or f"Execute {action.description}?"

        # Build prompt
        full_prompt = f"{prompt_text} Say YES to approve or NO to cancel."
        if risk == "high":
            full_prompt = f"Warning: High risk action! {prompt_text} Please confirm: Say YES to proceed or NO to abort."

        print(f"\n[Permission Required - {risk.upper()} RISK]: {full_prompt}")

        # Speak prompt synchronously so mic never hears the prompt
        if self.speaker:
            loop = asyncio.get_running_loop()
            if hasattr(self.speaker, "speak_sync"):
                await loop.run_in_executor(None, self.speaker.speak_sync, full_prompt)
            else:
                self.speaker.speak(full_prompt)

        await asyncio.sleep(0.2)

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
                loop = asyncio.get_running_loop()
                if hasattr(self.speaker, "speak_sync"):
                    await loop.run_in_executor(None, self.speaker.speak_sync, double_prompt)
                else:
                    self.speaker.speak(double_prompt)

            await asyncio.sleep(0.2)

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
        act_id = getattr(action, "action_id", "")
        self._pending_remote_requests[request_id] = {
            "future": future,
            "action_id": act_id,
            "action": action
        }

        payload = {
            "type": "permission_request",
            "request_id": request_id,
            "action_id": act_id,
            "action_type": action.action_type,
            "description": action.description,
            "parameters": action.parameters,
            "risk_level": action.risk_level,
            "message": describe_action(action) if action.risk_level.lower() in ("medium", "high") else (action.confirmation_message or f"Approve {action.description}?")
        }
        return request_id, payload, future

    def resolve_remote_permission(self, request_id: str, approved: bool, action_id: Optional[str] = None) -> bool:
        """Called when a remote client sends permission_response."""
        entry = self._pending_remote_requests.pop(request_id, None)
        if not entry:
            return False

        if isinstance(entry, dict):
            future = entry.get("future")
            expected_action_id = entry.get("action_id")
        else:
            future = entry
            expected_action_id = None

        if action_id is not None and expected_action_id:
            if action_id != expected_action_id:
                logger.warning(
                    f"Action ID mismatch for request '{request_id}': expected '{expected_action_id}', got '{action_id}'"
                )
                if future and not future.done():
                    future.set_result(False)
                return False

        if future and not future.done():
            future.set_result(approved)
            return True
        return False

    def cancel_all_pending(self, reason: str = "Aborted by user"):
        """Cancel and resolve all pending permission futures with False."""
        for req_id, entry in list(self._pending_remote_requests.items()):
            future = entry.get("future") if isinstance(entry, dict) else entry
            if future and not future.done():
                future.set_result(False)
        self._pending_remote_requests.clear()
        logger.info(f"Cancelled all pending permission requests: {reason}")



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
