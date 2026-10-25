"""
🎙️ Voice Agent — Main Entry Point
Supports:
  1. Local voice-controlled execution with spoken permission gates.
  2. Remote mobile web server with Web Speech API and button approvals.
  3. Concurrent dual-mode running both local and remote interfaces simultaneously.
"""

import argparse
import asyncio
import logging
import signal
import sys
import threading
from typing import Optional
import uvicorn

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import config
from voice.speaker import VoiceSpeaker
from voice.listener import VoiceListener
from brain import ZenoBrain, ActionPlanner, NLUEngine
from executor.task_executor import TaskExecutor
from logging.handlers import RotatingFileHandler
from executor.permissions import PermissionManager
from executor.agent_runner import AgentRunner, coordinator
from brain.planner import describe_action
from voice.listener import parse_confirmation
from tunnel.tunnel_manager import TunnelManager

def setup_logging(log_file: Optional[str] = None, max_bytes: int = 5 * 1024 * 1024, backup_count: int = 5):
    """Configure console and rotating file logging."""
    target_file = log_file or config.LOG_FILE
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        target_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)

    return [stream_handler, file_handler]

setup_logging()
logger = logging.getLogger("VoiceAgent.Main")


class VoiceAgentApp:
    def __init__(self, mode: str = "all", port: int = config.SERVER_PORT):
        self.mode = mode
        self.port = port
        self.running = False

        # Initialize subsystems
        self.speaker = VoiceSpeaker()
        self.listener = VoiceListener(model_size=config.WHISPER_MODEL)
        self.listener.tts_state = self.speaker.speech_state
        self.executor = TaskExecutor()
        self.brain = ZenoBrain(executor=self.executor)
        self.planner = self.brain.planner
        self.nlu = self.brain.nlu
        self.permissions = PermissionManager(listener=self.listener, speaker=self.speaker)
        self.tunnel_manager = TunnelManager(port=self.port)
        self.server_thread = None
        self._local_approval = None
        self._local_task = None

    def print_banner(self):
        banner = r"""
  ███████╗███████╗███╗   ██╗ ██████╗ 
  ╚══███╔╝██╔════╝████╗  ██║██╔═══██╗
    ███╔╝ █████╗  ██╔██╗ ██║██║   ██║
   ███╔╝  ██╔══╝  ██║╚██╗██║██║   ██║
  ███████╗███████╗██║ ╚████║╚██████╔╝
  ╚══════╝╚══════╝╚═╝  ╚═══╝ ╚═════╝ 
        """
        print(banner)
        print("=" * 64)
        print(f"  🎙️ {config.ASSISTANT_NAME} — COGNITIVE AUTONOMOUS ASSISTANT")
        print("=" * 64)
        print(f"  • Operating Mode     : {self.mode.upper()}")
        print(f"  • Microphone Ready   : {'YES' if self.listener.is_mic_available() else 'NO (Console Fallback)'}")
        print(f"  • Gemini AI Brain    : {'Online' if config.GEMINI_API_KEY else 'Offline (Local Rules Fallback)'}")
        print(f"  • Cognitive Memory   : Online (Short-term context + Long-term facts)")
        print(f"  • Multimodal Vision  : {'Active' if config.GEMINI_API_KEY else 'Basic Screen Telemetry'}")
        print(f"  • Ngrok Auth Token   : {'Configured' if config.NGROK_AUTH_TOKEN else 'None (LAN Only)'}")
        print("  • Access Token       : [Configured in .env]")
        print("=" * 64)

    def start_web_server(self):
        """Start FastAPI uvicorn server in a background thread."""
        logger.info(f"Starting Remote Web Server on {config.SERVER_HOST}:{self.port}...")
        
        # Start ngrok tunnel if token is set
        tunnel_url = self.tunnel_manager.start_tunnel()
        local_url = self.tunnel_manager.get_local_url()

        print("\n🌐 REMOTE CONTROL ACCESS:")
        print(f"   Local Wi-Fi URL : {local_url}")
        if tunnel_url:
            print(f"   Public Tunnel   : {tunnel_url}")
            self.speaker.speak("Remote control tunnel is live. Check your console for the link.")
        else:
            print("   Public Tunnel   : Disabled (set NGROK_AUTH_TOKEN in .env to enable)")
        print("   Passphrase      : Passphrase is in .env\n")

        # Share existing subsystem singletons with web server
        from server.app import init_shared_subsystems
        init_shared_subsystems(
            executor=self.executor,
            brain=self.brain,
            permissions=self.permissions,
            speaker=self.speaker,
            planner=self.planner
        )

        uv_config = uvicorn.Config(
            "server.app:app",
            host=config.SERVER_HOST,
            port=self.port,
            log_level="warning"
        )
        server = uvicorn.Server(uv_config)

        def run_server():
            asyncio.run(server.serve())

        self.server_thread = threading.Thread(target=run_server, daemon=True, name="Uvicorn-Server")
        self.server_thread.start()

    async def process_user_command(self, user_text: str):
        """End-to-end processing pipeline for a spoken or typed command."""
        print(f"\n👤 [User]: \"{user_text}\"")

        # Step 1: Cognitive Processing via ZENO Brain
        brain_resp = await self.brain.think(user_text)

        if brain_resp.kind == "abort":
            coordinator.stop()
            self.permissions.cancel_all_pending("Aborted by user command")
            print(f"🛑 [{config.ASSISTANT_NAME}]: {brain_resp.message}")
            self.speaker.speak(brain_resp.message)
            return

        # Handle Conversational, Vision, or Memory responses directly
        if brain_resp.kind in ("chat", "vision", "memory"):
            print(f"🧠 [{config.ASSISTANT_NAME}]: {brain_resp.message}")
            self.speaker.speak(brain_resp.message)
            return


        async def emit(event):
            message = event.get("message", "")
            print(f"[{event.get('status', 'ZENO')}] {message}")
            if event["type"] == "response" or event.get("status") in ("completed", "blocked", "needs_input", "failed"):
                self.speaker.speak(message)

        runner = AgentRunner(self.brain, self.permissions, "local", self.approve_local_task, emit)
        await runner.run((brain_resp.data or {}).get("goal", user_text),
                         actions=brain_resp.actions, agent_mode=brain_resp.kind == "task")

    async def approve_local_task(self, action):
        """The single local input loop owns the mic and routes yes/no responses here."""
        rounds = 2 if action.risk_level == "high" else 1
        approved = False
        try:
            for stage in range(rounds):
                prompt = ("Final confirmation. " if stage else "") + describe_action(action) + ". Say yes or no."
                self._local_approval = asyncio.get_running_loop().create_future()
                print(f"\n[Approval] {prompt}")
                self.speaker.speak(prompt)
                try:
                    approved = await asyncio.wait_for(self._local_approval, config.REMOTE_CONFIRMATION_TIMEOUT)
                except asyncio.TimeoutError:
                    approved = False
                if not approved:
                    break
            self.permissions.log_decision(action, approved, source="local")
            return approved
        finally:
            self._local_approval = None

    async def run_local_loop(self):
        """Continuous local voice/keyboard control loop."""
        self.speaker.speak(f"{config.ASSISTANT_NAME} is active and standing by.")
        print(f"\n🎧 {config.ASSISTANT_NAME} is listening. Speak clearly or type a command below.")
        print("   (Press Ctrl+C at any time to exit)\n")

        while self.running:
            try:
                # Listen for speech or console input
                loop = asyncio.get_running_loop()
                text = await loop.run_in_executor(
                    None,
                    self.listener.listen_once,
                    config.LISTEN_TIMEOUT,
                    config.PHRASE_TIMEOUT
                )

                if text and text.strip():
                    text = text.strip()
                    clean = self.brain.strip_wake_prefix(text).lower().strip(" .!?,")
                    if clean in ("stop", "cancel", "cancel everything", "abort", "halt", "kill", "emergency stop"):
                        coordinator.stop()
                        if self._local_task and not self._local_task.done():
                            self._local_task.cancel()
                        print("[ZENO] Stop requested. No further steps will run.")
                        continue
                    if self._local_approval is not None and not self._local_approval.done():
                        decision = parse_confirmation(text)
                        if decision is not None:
                            self._local_approval.set_result(decision)
                        else:
                            print("[ZENO] Please say yes, no, or stop.")
                    elif self._local_task and not self._local_task.done():
                        print("[ZENO] A task is running. Say stop to cancel it.")
                    else:
                        self._local_task = asyncio.create_task(self.process_user_command(text))
                        # Retrieve exceptions without leaving a background task warning.
                        self._local_task.add_done_callback(self._local_task_finished)
                await asyncio.sleep(0.05)

            except (KeyboardInterrupt, asyncio.CancelledError):
                break
            except Exception as e:
                logger.error(f"Error in local processing loop: {e}")
                await asyncio.sleep(1)

    @staticmethod
    def _local_task_finished(task):
        if not task.cancelled() and task.exception():
            logger.error("Local task failed: %s", task.exception())

    def shutdown(self):
        """Clean shutdown of all subsystems."""
        print("\n🛑 Shutting down Voice Agent gracefully...")
        self.running = False
        coordinator.stop()
        self.listener.stop()
        self.speaker.stop()
        self.tunnel_manager.stop_tunnel()
        print("👋 Goodbye!")

    def run(self):
        """Main launch entry point."""
        self.print_banner()

        # Display configuration warnings if any
        warnings = config.validate()
        for w in warnings:
            print(w)

        self.running = True

        # Start web server if mode is 'all' or 'server'
        if self.mode in ("all", "server"):
            self.start_web_server()

        if self.mode == "server":
            print("\n🚀 Server-only mode running. Access via web UI.")
            print("   Press Ctrl+C to stop.")
            try:
                while self.running:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                self.shutdown()
        else:
            # Run local asyncio loop
            try:
                asyncio.run(self.run_local_loop())
            except KeyboardInterrupt:
                pass
            finally:
                self.shutdown()


def main():
    parser = argparse.ArgumentParser(description="Voice Agent - Autonomous Secure Voice Control")
    parser.add_argument(
        "--mode",
        choices=["all", "local", "server"],
        default="all",
        help="Operating mode: 'all' (local voice + remote web), 'local' (voice only), 'server' (web only)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=config.SERVER_PORT,
        help=f"Port for the remote web server (default: {config.SERVER_PORT})"
    )
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Run microphone noise calibration before starting"
    )
    args = parser.parse_args()

    agent = VoiceAgentApp(mode=args.mode, port=args.port)

    if args.calibrate:
        print("🎤 Calibrating microphone for ambient noise...")
        agent.listener.calibrate(duration=3.0)

    agent.run()


if __name__ == "__main__":
    main()
