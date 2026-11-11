"""
FastAPI Server for Voice Agent Remote Control.
Handles mobile Web UI serving, JWT authentication, and real-time bidirectional WebSocket
communication with permission negotiation.
"""

import json
import ipaddress
import logging
import asyncio
import uuid
import time
import copy
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Form, HTTPException, status, Request, Header
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .remote_access import owner_approves
from brain.planner import PlannedAction
import app_access
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
from executor.history import audit_files
from executor.agent_runner import AgentRunner, coordinator
from voice.speaker import VoiceSpeaker

logger = logging.getLogger("VoiceAgent.Server")

app = FastAPI(title="ZENO Remote Control", version="2.0.0")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

remote_grant = None


def trusted_endpoint(connection):
    if remote_grant is None:
        return False
    host = connection.headers.get("host", "")
    origin = connection.headers.get("origin")
    scheme = "http" if host.split(":")[0] in {"localhost", "127.0.0.1"} else "https"
    expected = f"{scheme}://{host}"
    if scheme == "https" and connection.headers.get("x-forwarded-proto") != "https":
        return False
    return expected in remote_grant.origins and (origin is None or origin == expected)


@app.middleware("http")
async def check_endpoint(request, call_next):
    if not trusted_endpoint(request):
        return JSONResponse({"detail": "Unrecognized workspace address."}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    host = request.headers["host"]
    socket_scheme = "ws" if host.split(":")[0] in {"localhost", "127.0.0.1"} else "wss"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; base-uri 'none'; object-src 'none'; "
        "frame-ancestors 'none'; form-action 'self'; img-src 'self' data: blob:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        f"font-src 'self' https://fonts.gstatic.com; connect-src 'self' {socket_scheme}://{host}"
    )
    return response


def get_client_ip(request: Request) -> str:
    """Extract client IP, trusting X-Forwarded-For only when behind local proxy / ngrok."""
    direct_ip = request.client.host if request.client else "127.0.0.1"
    is_proxy = direct_ip in ("127.0.0.1", "::1", "localhost")
    if is_proxy:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            try:
                return str(ipaddress.ip_address(xff.split(",")[-1].strip()))
            except ValueError:
                pass
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
async def authenticate(request: Request, token: str = Form(...), pairing_code: str = Form(default=""), device_id: str = Form(default=""), device_label: str = Form(default="Unnamed device")):
    """Pair an identified device after passphrase validation and issue a scoped session."""
    client_ip = get_client_ip(request)
    if auth_manager.verify_passphrase(token, client_id=client_ip):
        grant = remote_grant
        if not grant.consume(pairing_code):
            raise HTTPException(403, "A fresh code from the PC terminal is required.")
        if not await asyncio.to_thread(owner_approves, f"Allow this browser ({client_ip}) {grant.scope} access for this session?"):
            raise HTTPException(403, "Pairing was declined or timed out. Restart server mode for a new code.")
        if not grant.active():
            raise HTTPException(403, "Session ended.")
        try:
            # Kept for older clients; current UI always supplies a random stable ID.
            device_id = device_id or f"legacy-{client_ip}"
            device = device_registry.pair(device_id, device_label, client_ip)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        grant.last_activity = time.monotonic()
        jwt_token = auth_manager.create_session_token(client_id=client_ip, device_id=device_id, generation=device["generation"], grant_id=grant.id)
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
async def health_check(authorization: Optional[str] = Header(None)):
    """Health status and telemetry endpoint, protected by JWT."""
    jwt_val = None
    if authorization and authorization.startswith("Bearer "):
        jwt_val = authorization[len("Bearer "):].strip()
    if not verified_session(jwt_val):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for health endpoint."
        )

    if remote_grant.scope != "controller" or not app_access.allowed("system"):
        return {"status": "healthy", "cpu_percent": None, "ram_percent": None, "battery": None}
    battery = psutil.sensors_battery()
    return {
        "status": "healthy",
        "cpu_percent": psutil.cpu_percent(),
        "ram_percent": psutil.virtual_memory().percent,
        "battery": battery.percent if battery else None
    }


def verified_session(token: str, client_ip: str = "") -> Optional[Dict[str, Any]]:
    if not isinstance(token, str):
        return None
    payload = auth_manager.verify_session_token(token)
    if not payload or not isinstance(payload.get("exp"), (float, int)) or payload["exp"] <= time.time():
        return None
    if not remote_grant or not remote_grant.active() or payload.get("grant_id") != remote_grant.id:
        return None
    if not device_registry.accepts_session(payload.get("device_id", ""), payload.get("generation", "")):
        return None
    if client_ip:
        device_registry.touch(payload["device_id"], client_ip)
    return payload


@app.get("/api/devices")
async def paired_devices(authorization: Optional[str] = Header(None)):
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not verified_session(token):
        raise HTTPException(status_code=401, detail="Authentication required.")
    if remote_grant.scope != "controller":
        raise HTTPException(403, "Controller access required.")
    return {"devices": device_registry.list_safe()}


@app.delete("/api/devices/{device_id}")
async def revoke_device(device_id: str, authorization: Optional[str] = Header(None)):
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    payload = verified_session(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Authentication required.")
    if remote_grant.scope != "controller":
        raise HTTPException(403, "Controller access required.")
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
    if remote_grant.scope != "controller":
        raise HTTPException(403, "Controller access required.")
    limit = max(1, min(limit, 500))
    events, skipped, truncated = [], 0, False
    remaining_bytes = 4 * 1024 * 1024
    for path in audit_files():
        if len(events) >= limit:
            break
        if remaining_bytes == 0:
            truncated = True
            break
        with path.open("rb") as stream:
            end = stream.seek(0, 2)
            floor = max(0, end - remaining_bytes)
            remaining_bytes -= end - floor
            partial = b""
            while end > floor and len(events) < limit:
                start = max(floor, end - 65536)
                stream.seek(start)
                lines = (stream.read(end - start) + partial).split(b"\n")
                partial = lines.pop(0) if start else b""
                for line in reversed(lines):
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                        if not isinstance(event, dict):
                            raise ValueError("Expected an event object")
                        events.append(event)
                    except (ValueError, UnicodeError):
                        skipped += 1
                    if len(events) == limit:
                        break
                end = start
            truncated = floor > 0 and len(events) < limit
    return {"events": list(reversed(events)), "skipped": skipped, "truncated": truncated}


@app.get("/audit", response_class=HTMLResponse)
async def serve_audit_dashboard():
    """The data itself remains protected by /api/audit authentication."""
    path = TEMPLATE_PATH.parent / "audit.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audit dashboard template not found.")
    return HTMLResponse(path.read_text(encoding="utf-8"))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time bi-directional channel for remote voice/text control."""
    if not trusted_endpoint(websocket) or "token" in websocket.query_params:
        await websocket.close(code=4003)
        return
    await websocket.accept()
    try:
        message = json.loads(await asyncio.wait_for(websocket.receive_text(), timeout=10))
        token = message.get("token") if isinstance(message, dict) and message.get("type") == "auth" else None
        auth_payload = verified_session(token, websocket.client.host if websocket.client else "")
    except (ValueError, TypeError, asyncio.TimeoutError, WebSocketDisconnect):
        auth_payload = None
    if not auth_payload:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    await websocket.send_json({"type": "auth_ok", "scope": remote_grant.scope})
    logger.info(f"Remote client connected via WebSocket (user: {auth_payload.get('sub', 'unknown')}).")

    task_exec, planner, brain, perms, speaker = get_subsystems()
    brain = copy.copy(brain)
    from awareness.gmail import GmailMailbox
    brain.gmail_mailbox = GmailMailbox(approve_send=lambda review: owner_approves(review) and bool(verified_session(token)))
    brain.pending_folder_location = None
    brain.awaiting_clarification = False
    brain.memory = copy.copy(brain.memory)
    brain.memory.short_term_history = []
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
        status = "responded"
        try:
            if remote_grant.scope == "media":
                commands = {"play": "play", "pause": "pause", "next": "next", "previous": "previous",
                            "stop": "stop", "play music": "play", "pause music": "pause", "next track": "next",
                            "previous track": "previous", "stop music": "stop"}
                command = commands.get(user_text.casefold())
                if not command:
                    status = "blocked"
                    await send_to_client({"type": "response", "message": "Media access allows play, pause, next, previous and stop."})
                    return
                result = await asyncio.to_thread(task_exec.execute, PlannedAction("media_control", {"command": command}))
                if result.success:
                    remote_grant.last_activity = time.monotonic()
                status = "completed" if result.success else "blocked"
                await send_to_client({"type": "response", "message": result.message})
                return
            if not await asyncio.to_thread(owner_approves, f"Allow ZENO to process this remote request?\n\n{user_text}") or not verified_session(token):
                status = "blocked"
                await send_to_client({"type": "response", "message": "PC approval was declined or expired."})
                return
            remote_grant.last_activity = time.monotonic()
            brain_resp = await brain.think(user_text, agent_mode=True) if agent_mode else await brain.think(user_text)
            if brain_resp.kind in ("chat", "vision", "memory", "abort"):
                if brain_resp.kind == "abort":
                    coordinator.stop(connection_id)
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
                if approved:
                    details = json.dumps({"action": action.action_type, "parameters": action.parameters}, ensure_ascii=False, indent=2)
                    approved = await asyncio.to_thread(owner_approves, "Allow this remote action?\n\n" + details)
                return approved and bool(verified_session(token))

            async def emit(event):
                await send_to_client(event)
                if event["type"] == "response" or event.get("status") in ("completed", "blocked", "needs_input", "failed"):
                    speaker.speak(event.get("message", ""))

            runner = AgentRunner(brain, perms, connection_id, approve, emit, planner=planner)
            status = await runner.run((brain_resp.data or {}).get("goal", brain_resp.message if brain_resp.kind == "task" else user_text),
                             actions=brain_resp.actions, agent_mode=brain_resp.kind == "task" or bool((brain_resp.data or {}).get("agent_mode")))
            following = (brain_resp.data or {}).get('following_mail')
            if status == 'completed' and following:
                await emit({"type": "response", "message": await brain.respond_to_mail(following)})
        except asyncio.CancelledError:
            status = "cancelled"
            raise
        except Exception:
            status = "failed"
            logger.exception("Command processing failed")
            await send_to_client({"type": "response", "message": "The command could not be processed. Please try again."})
        finally:
            await send_to_client({"type": "command_finished", "status": status})

    try:
        while True:
            remaining = auth_payload["exp"] - time.time()
            if remaining <= 0:
                await websocket.close(code=4001, reason="Session expired")
                break
            try:
                raw_data = await asyncio.wait_for(websocket.receive_text(), timeout=min(remaining, 2))
            except asyncio.TimeoutError:
                raw_data = None
            if not remote_grant.active() or time.time() >= auth_payload["exp"]:
                await websocket.close(code=4001, reason="Session expired")
                break
            if not device_registry.accepts_session(device_id, auth_payload.get("generation", "")):
                await websocket.close(code=4003, reason="Device revoked")
                break
            if raw_data is None:
                continue
            try:
                msg = json.loads(raw_data)
            except Exception:
                continue

            if not isinstance(msg, dict):
                continue
            msg_type = msg.get("type")
            text_value = msg.get("text", "")
            if remote_grant.scope == "media" and msg_type not in {"command", "get_telemetry"}:
                continue
            if remote_grant.scope == "controller" and msg_type == "command" and isinstance(text_value, str):
                stop_text = brain.strip_wake_prefix(text_value).lower().strip(" .!?,")
                if stop_text in ("stop", "cancel", "cancel everything", "abort", "halt", "kill", "emergency stop"):
                    msg_type = "abort"


            # Telemetry request
            if msg_type == "get_telemetry":
                if remote_grant.scope != "controller" or not app_access.allowed("system"):
                    await send_to_client({"type": "telemetry", "cpu": None, "ram": None, "battery": None})
                    continue
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
                brain.pending_folder_location = None
                brain.awaiting_clarification = False
                coordinator.stop(connection_id)
                for t in list(active_tasks):
                    if not t.done():
                        t.cancel()
                active_tasks.clear()
                for request_id in owned_requests:
                    perms.resolve_remote_permission(request_id, False, device_id=device_id)
                owned_requests.clear()
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
                if isinstance(req_id, str) and req_id in owned_requests:
                    owned_requests.discard(req_id)
                    perms.resolve_remote_permission(req_id, approved, action_id=action_id, device_id=device_id)
                continue

            # Voice or text command - processed in background task so receive loop never blocks
            if msg_type == "command":
                if not isinstance(text_value, str):
                    continue
                user_text = text_value.strip()
                if not user_text or len(user_text) > 12000:
                    await send_to_client({"type": "error", "message": "Enter a command of 1 to 12,000 characters."})
                    continue
                if msg.get('mode') == 'chat':
                    from brain.companion import conversation_text
                    if conversation_text(user_text) is None:
                        user_text = 'Chat: ' + user_text

                if active_tasks or coordinator.active is not None:
                    await send_to_client({"type": "response", "message": "ZENO is busy. Stop the current task or wait for it to finish."})
                    if not active_tasks:
                        await send_to_client({"type": "command_finished", "status": "blocked"})
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
