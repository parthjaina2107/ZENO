"""
FastAPI Server for Voice Agent Remote Control.
Handles mobile Web UI serving, JWT authentication, and real-time bidirectional WebSocket
communication with permission negotiation.
"""

import json
import logging
import asyncio
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Form, HTTPException, status, Request, Header
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import psutil

from config import config
from .auth import auth_manager
from .pairing import device_registry
from brain import ZenoBrain, ActionPlanner, NLUEngine
from brain.planner import describe_action
from brain.task_runner import TaskRunner
from brain.interaction import action_record, outcome_reply
from executor.task_executor import TaskExecutor
from executor.permissions import PermissionManager
from executor.agent_runner import AgentRunner, coordinator
from voice.speaker import VoiceSpeaker

logger = logging.getLogger("VoiceAgent.Server")

app = FastAPI(title="ZENO Remote Control", version="2.0.0")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Restrict CORS to own origins and ngrok proxy domains
ALLOWED_ORIGINS = [
    f"http://localhost:{config.SERVER_PORT}",
    f"http://127.0.0.1:{config.SERVER_PORT}",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"^https?://([a-zA-Z0-9-]+\.)?ngrok(-free)?\.(app|io)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def get_client_ip(request: Request) -> str:
    """Extract client IP, trusting X-Forwarded-For only when behind local proxy / ngrok."""
    direct_ip = request.client.host if request.client else "127.0.0.1"
    is_proxy = direct_ip in ("127.0.0.1", "::1", "localhost", "testclient") or "ngrok-trace-id" in request.headers or "x-forwarded-proto" in request.headers
    if is_proxy:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
    return direct_ip

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
async def authenticate(request: Request, token: str = Form(...), device_id: str = Form(default=""), device_label: str = Form(default="Unnamed device")):
    """Pair an identified device after passphrase validation and issue a scoped session."""
    client_ip = get_client_ip(request)
    if auth_manager.verify_passphrase(token, client_id=client_ip):
        try:
            # Kept for older clients; current UI always supplies a random stable ID.
            device_id = device_id or f"legacy-{client_ip}"
            device = device_registry.pair(device_id, device_label, client_ip)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        jwt_token = auth_manager.create_session_token(client_id=client_ip, device_id=device_id)
        return JSONResponse(content={"status": "authenticated", "jwt_token": jwt_token, "device": device})
    else:
        locked, remaining = auth_manager.is_locked_out(client_ip)
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
async def health_check(authorization: Optional[str] = Header(None), token: Optional[str] = None):
    """Health status and telemetry endpoint, protected by JWT."""
    jwt_val = None
    if authorization and authorization.startswith("Bearer "):
        jwt_val = authorization[len("Bearer "):].strip()
    elif token:
        jwt_val = token.strip()

    payload = auth_manager.verify_session_token(jwt_val) if jwt_val else None
    if not payload or not device_registry.is_active(payload.get("device_id", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for health endpoint."
        )

    battery = psutil.sensors_battery()
    return {
        "status": "healthy",
        "cpu_percent": psutil.cpu_percent(),
        "ram_percent": psutil.virtual_memory().percent,
        "battery": battery.percent if battery else None
    }


def verified_session(token: str, client_ip: str = "") -> Optional[Dict[str, Any]]:
    payload = auth_manager.verify_session_token(token)
    if not payload or not device_registry.is_active(payload.get("device_id", "")):
        return None
    if client_ip:
        device_registry.touch(payload["device_id"], client_ip)
    return payload


@app.get("/api/devices")
async def paired_devices(authorization: Optional[str] = Header(None)):
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not verified_session(token):
        raise HTTPException(status_code=401, detail="Authentication required.")
    return {"devices": device_registry.list_safe()}


@app.delete("/api/devices/{device_id}")
async def revoke_device(device_id: str, authorization: Optional[str] = Header(None)):
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    payload = verified_session(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Authentication required.")
    if payload.get("device_id") == device_id:
        raise HTTPException(status_code=400, detail="Use another paired device to revoke this device.")
    if not device_registry.revoke(device_id):
        raise HTTPException(status_code=404, detail="Device not found.")
    return {"status": "revoked"}


@app.get("/api/audit")
async def read_audit(limit: int = 100, authorization: Optional[str] = Header(None)):
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not verified_session(token):
        raise HTTPException(status_code=401, detail="Authentication required.")
    limit = max(1, min(limit, 500))
    path = config.BASE_DIR / "audit_log.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
        return {"events": [json.loads(line) for line in lines if line.strip()]}
    except FileNotFoundError:
        return {"events": []}


@app.get("/audit", response_class=HTMLResponse)
async def serve_audit_dashboard():
    """The data itself remains protected by /api/audit authentication."""
    path = TEMPLATE_PATH.parent / "audit.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audit dashboard template not found.")
    return HTMLResponse(path.read_text(encoding="utf-8"))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = None):
    """Real-time bi-directional channel for remote voice/text control."""
    await websocket.accept()

    auth_payload = None
    if token:
        auth_payload = verified_session(token, websocket.client.host if websocket.client else "")

    if not auth_payload:
        # Await first WebSocket message containing {"type": "auth", "token": "..."}
        try:
            raw_first = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
            msg_first = json.loads(raw_first)
            cand_token = msg_first.get("token") or (msg_first.get("text") if msg_first.get("type") == "auth" else None)
            if cand_token:
                auth_payload = verified_session(cand_token, websocket.client.host if websocket.client else "")
            if not auth_payload:
                logger.warning("Rejected unauthorized WebSocket: invalid first message auth.")
                await websocket.send_text(json.dumps({"type": "error", "message": "Unauthorized"}))
                await websocket.close(code=4001, reason="Unauthorized")
                return
            else:
                await websocket.send_text(json.dumps({"type": "auth_ok"}))
        except Exception as e:
            logger.warning(f"WebSocket auth handshake timed out or failed: {e}")
            await websocket.close(code=4001, reason="Unauthorized")
            return

    logger.info(f"Remote client connected via WebSocket (user: {auth_payload.get('sub', 'unknown')}).")

    task_exec, planner, brain, perms, speaker = get_subsystems()
    device_id = auth_payload["device_id"]
    active_tasks = set()
    connection_id = "remote:" + uuid.uuid4().hex
    owned_requests = set()


    async def send_to_client(data: Dict[str, Any]):
        try:
            if data.get("type") == "permission_request":
                owned_requests.add(data["request_id"])
            await websocket.send_text(json.dumps(data))
        except Exception as e:
            logger.error(f"Failed to send to client: {e}")

    async def handle_command(user_text: str, agent_mode=False):
        """Keep receiving approvals and stop commands while planning/execution runs."""
        try:
            brain_resp = await brain.think(user_text, agent_mode=True) if agent_mode else await brain.think(user_text)
            if brain_resp.kind in ("chat", "vision", "memory", "abort"):
                if brain_resp.kind == "abort":
                    coordinator.stop()
                speaker.speak(brain_resp.message)
                await send_to_client({"type": "response", "message": brain_resp.message, "kind": brain_resp.kind})
                return

            async def approve(action):
                approved = await perms.request_permission_remote(action, send_to_client, config.REMOTE_CONFIRMATION_TIMEOUT, device_id=device_id)
                if approved and action.risk_level == "high":
                    async def send_final(payload):
                        payload["message"] = "Final confirmation: " + payload["message"]
                        await send_to_client(payload)
                    approved = await perms.request_permission_remote(action, send_final, config.REMOTE_CONFIRMATION_TIMEOUT, device_id=device_id)
                return approved

            async def emit(event):
                await send_to_client(event)
                if event["type"] == "response" or event.get("status") in ("completed", "blocked", "needs_input", "failed"):
                    speaker.speak(event.get("message", ""))

            runner = AgentRunner(brain, perms, connection_id, approve, emit, planner=planner)
            await runner.run((brain_resp.data or {}).get("goal", brain_resp.message if brain_resp.kind == "task" else user_text),
                             actions=brain_resp.actions, agent_mode=brain_resp.kind == "task")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Command processing failed")
            await send_to_client({"type": "response", "message": "The command could not be processed. Please try again."})
        finally:
            await send_to_client({"type": "command_finished"})

    try:
        while True:
            raw_data = await websocket.receive_text()
            if not device_registry.is_active(device_id):
                await websocket.close(code=4003, reason="Device revoked")
                break
            try:
                msg = json.loads(raw_data)
            except Exception:
                continue

            if not isinstance(msg, dict):
                continue
            msg_type = msg.get("type")
            text_value = msg.get("text", "")
            if msg_type == "command" and isinstance(text_value, str):
                stop_text = brain.strip_wake_prefix(text_value).lower().strip(" .!?,")
                if stop_text in ("stop", "cancel", "cancel everything", "abort", "halt", "kill", "emergency stop"):
                    msg_type = "abort"


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

            # Abort / Emergency stop
            if msg_type == "abort":
                logger.warning("Emergency abort received over WebSocket.")
                coordinator.stop()
                for t in list(active_tasks):
                    if not t.done():
                        t.cancel()
                active_tasks.clear()
                perms.cancel_all_pending("Emergency abort via WebSocket")
                speaker.speak("Emergency stop. No further steps will run.")
                await send_to_client({
                    "type": "response",
                    "message": "🛑 Emergency stop: queued actions aborted. An action already in progress may finish.",
                    "kind": "abort"
                })
                continue

            # Permission response from client button click
            if msg_type == "permission_response":
                req_id = msg.get("request_id")
                approved = msg.get("approved") is True
                action_id = msg.get("action_id")
                if req_id in owned_requests:
                    owned_requests.discard(req_id)
                    perms.resolve_remote_permission(req_id, approved, action_id=action_id, device_id=device_id)
                continue

            # Voice or text command - processed in background task so receive loop never blocks
            if msg_type == "command":
                if not isinstance(text_value, str):
                    continue
                user_text = text_value.strip()
                if not user_text or len(user_text) > 12000:
                    continue
                if msg.get('mode') == 'chat':
                    from brain.companion import conversation_text
                    if conversation_text(user_text) is None:
                        user_text = 'Chat: ' + user_text

                if active_tasks or coordinator.active is not None:
                    await send_to_client({"type": "response", "message": "ZENO is busy. Stop the current task or wait for it to finish."})
                    continue
                task = asyncio.create_task(handle_command(user_text, agent_mode=msg.get("mode") == "agent"))
                active_tasks.add(task)
                task.add_done_callback(active_tasks.discard)

    except WebSocketDisconnect:
        logger.info("Remote client disconnected.")
    except Exception as e:
        logger.exception(f"Unexpected WebSocket error: {e}")
    finally:
        coordinator.stop(connection_id)
        for request_id in owned_requests:
            perms.resolve_remote_permission(request_id, False, device_id=device_id)
        for t in list(active_tasks):
            if not t.done():
                t.cancel()
        active_tasks.clear()
