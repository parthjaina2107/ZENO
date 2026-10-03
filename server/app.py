"""
FastAPI Server for Voice Agent Remote Control.
Handles mobile Web UI serving, JWT authentication, and real-time bidirectional WebSocket
communication with permission negotiation.
"""

import json
import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Form, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import psutil

# Module-level execution lock to serialize command execution across connections
EXEC_LOCK = asyncio.Lock()

from config import config
from .auth import auth_manager
from brain import ZenoBrain, ActionPlanner, NLUEngine
from executor.task_executor import TaskExecutor
from executor.permissions import PermissionManager
from voice.speaker import VoiceSpeaker

logger = logging.getLogger("VoiceAgent.Server")

app = FastAPI(title="ZENO Remote Control", version="2.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared subsystems (initialized from main.py or initialized lazily on-demand)
task_executor = None
action_planner = None
zeno_brain = None
permission_manager = None
host_speaker = None


def init_shared_subsystems(executor=None, brain=None, permissions=None, speaker=None, planner=None):
    """Called from main.py to share existing subsystem instances across local and remote server."""
    global task_executor, action_planner, zeno_brain, permission_manager, host_speaker
    if executor is not None:
        task_executor = executor
    if brain is not None:
        zeno_brain = brain
    if permissions is not None:
        permission_manager = permissions
    if speaker is not None:
        host_speaker = speaker
    if planner is not None:
        action_planner = planner
    elif zeno_brain is not None:
        action_planner = zeno_brain.planner
    logger.info("Shared subsystems successfully initialized in server.")


def get_subsystems():
    """Ensure subsystems are initialized before handling requests."""
    global task_executor, action_planner, zeno_brain, permission_manager, host_speaker
    if task_executor is None:
        task_executor = TaskExecutor()
    if zeno_brain is None:
        zeno_brain = ZenoBrain(executor=task_executor)
    if action_planner is None:
        action_planner = zeno_brain.planner if hasattr(zeno_brain, "planner") else ActionPlanner(executor=task_executor)
    if permission_manager is None:
        permission_manager = PermissionManager()
    if host_speaker is None:
        host_speaker = VoiceSpeaker()
    return task_executor, action_planner, zeno_brain, permission_manager, host_speaker


# HTML template path
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "index.html"


@app.get("/", response_class=HTMLResponse)
async def serve_home():
    """Serve the mobile-friendly web control interface."""
    if not TEMPLATE_PATH.exists():
        raise HTTPException(status_code=404, detail="Template index.html not found.")
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/auth")
async def authenticate(token: str = Form(...)):
    """Authenticate with secret passphrase and receive a 24-hour JWT token."""
    if auth_manager.verify_passphrase(token):
        jwt_token = auth_manager.create_session_token()
        return JSONResponse(content={"status": "authenticated", "jwt_token": jwt_token})
    else:
        locked, remaining = auth_manager.is_locked_out("default")
        if locked:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed attempts. Locked out for {remaining} seconds."
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid secret access passphrase."
        )


@app.get("/health")
async def health_check():
    """Health status and telemetry endpoint."""
    battery = psutil.sensors_battery()
    return {
        "status": "healthy",
        "cpu_percent": psutil.cpu_percent(),
        "ram_percent": psutil.virtual_memory().percent,
        "battery": battery.percent if battery else None
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = None):
    """Real-time bi-directional channel for remote voice/text control."""
    # Step 1: Verify token
    if not token or not auth_manager.verify_session_token(token):
        logger.warning("Rejected unauthorized WebSocket connection attempt.")
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    logger.info("Remote client connected via WebSocket.")

    task_exec, planner, brain, perms, speaker = get_subsystems()
    active_tasks = set()

    async def send_to_client(data: Dict[str, Any]):
        try:
            await websocket.send_text(json.dumps(data))
        except Exception as e:
            logger.error(f"Failed to send to client: {e}")

    async def handle_command(user_text: str):
        """Execute command under global lock while allowing websocket to continue receiving."""
        async with EXEC_LOCK:
            logger.info(f"Remote command received: '{user_text}'")

            # Process via ZENO Cognitive Brain
            brain_resp = await brain.think(user_text)

            if brain_resp.kind in ("chat", "vision", "memory"):
                speaker.speak(brain_resp.message)
                await send_to_client({
                    "type": "response",
                    "message": brain_resp.message,
                    "kind": brain_resp.kind
                })
                return

            plan = brain_resp.actions
            for action in plan:
                if action.action_type in ("unhandled", "unknown"):
                    reply_msg = action.confirmation_message or "I didn't understand that command."
                    speaker.speak(reply_msg)
                    await send_to_client({
                        "type": "response",
                        "message": reply_msg
                    })
                    break

                if action.requires_permission:
                    # Auto-approve safe read-only actions
                    if action.action_type in getattr(config, "AUTO_APPROVE_ACTIONS", set()) and action.risk_level == "low":
                        perms.log_decision(action, True, source="auto", reason="Auto-approved safe read-only action")
                    else:
                        # Announce permission requirement
                        perm_msg = action.confirmation_message or f"Approval required to {action.description}."
                        speaker.speak(perm_msg)

                        # Request permission from phone
                        approved = await perms.request_permission_remote(
                            action=action,
                            send_func=send_to_client,
                            timeout=config.REMOTE_CONFIRMATION_TIMEOUT
                        )

                        if not approved:
                            cancel_msg = f"Action cancelled: '{action.description}' was denied or timed out."
                            speaker.speak(cancel_msg)
                            await send_to_client({
                                "type": "response",
                                "message": cancel_msg
                            })
                            break
                else:
                    if action.confirmation_message:
                        speaker.speak(action.confirmation_message)

                # Execute action
                result = planner.execute_action(action)

                if action.action_type == "screenshot" and result.success and isinstance(result.output, dict):
                    # Send screenshot base64 preview
                    speaker.speak(result.message)
                    await send_to_client({
                        "type": "screenshot",
                        "data": result.output.get("base64"),
                        "message": result.message
                    })
                else:
                    speaker.speak(result.message)
                    status_prefix = "✅ " if result.success else "❌ "
                    await send_to_client({
                        "type": "response",
                        "message": f"{status_prefix}{result.message}"
                    })

                if not result.success:
                    break

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                msg = json.loads(raw_data)
            except Exception:
                continue

            msg_type = msg.get("type")

            # Telemetry request
            if msg_type == "get_telemetry":
                battery = psutil.sensors_battery()
                cpu = psutil.cpu_percent()
                ram = psutil.virtual_memory().percent
                await send_to_client({
                    "type": "telemetry",
                    "cpu": cpu,
                    "ram": ram,
                    "battery": battery.percent if battery else None
                })
                continue

            # Permission response from client button click
            if msg_type == "permission_response":
                req_id = msg.get("request_id")
                approved = bool(msg.get("approved", False))
                perms.resolve_remote_permission(req_id, approved)
                continue

            # Voice or text command - processed in background task so receive loop never blocks
            if msg_type == "command":
                user_text = msg.get("text", "").strip()
                if not user_text:
                    continue

                task = asyncio.create_task(handle_command(user_text))
                active_tasks.add(task)
                task.add_done_callback(active_tasks.discard)

    except WebSocketDisconnect:
        logger.info("Remote client disconnected.")
    except Exception as e:
        logger.exception(f"Unexpected WebSocket error: {e}")
    finally:
        for t in list(active_tasks):
            if not t.done():
                t.cancel()
        active_tasks.clear()
