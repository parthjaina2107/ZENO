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
from executor.permissions import PermissionManager
from tunnel.tunnel_manager import TunnelManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.LOG_FILE, encoding="utf-8")
    ]
)
logger = logging.getLogger("VoiceAgent.Main")


class VoiceAgentApp:
    def __init__(self, mode: str = "all", port: int = config.SERVER_PORT):
        self.mode = mode
        self.port = port
        self.running = False

        # Initialize subsystems
        self.speaker = VoiceSpeaker()
        self.listener = VoiceListener(model_size=config.WHISPER_MODEL)
        self.executor = TaskExecutor()
        self.brain = ZenoBrain(executor=self.executor)
        self.planner = self.brain.planner
        self.nlu = self.brain.nlu
        self.permissions = PermissionManager(listener=self.listener, speaker=self.speaker)
        self.tunnel_manager = TunnelManager(port=self.port)
        self.server_thread = None

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

        # Handle Conversational, Vision, or Memory responses directly
        if brain_resp.kind in ("chat", "vision", "memory"):
            print(f"🧠 [{config.ASSISTANT_NAME}]: {brain_resp.message}")
            self.speaker.speak(brain_resp.message)
            return

        # Step 2: OS Automation Action Execution
        actions = brain_resp.actions
        for i, action in enumerate(actions):
            if action.action_type in ("unhandled", "unknown"):
                msg = action.confirmation_message or "I could not understand that command."
                print(f"🤖 [{config.ASSISTANT_NAME}]: {msg}")
                self.speaker.speak(msg)
                return

            # Step 3: Permission Gate (only for actions requiring approval)
            if action.requires_permission:
                # Auto-approve safe read-only actions
                if action.action_type in getattr(config, "AUTO_APPROVE_ACTIONS", set()) and action.risk_level == "low":
                    self.permissions.log_decision(action, True, source="auto", reason="Auto-approved safe read-only action")
                else:
                    approved = await self.permissions.request_permission_local(action)
                    if not approved:
                        cancel_msg = f"Cancelled: '{action.description}' was not approved."
                        print(f"❌ {cancel_msg}")
                        self.speaker.speak(cancel_msg)
                        return
            else:
                # Direct announcement for smooth assistant experience
                if action.confirmation_message:
                    self.speaker.speak(action.confirmation_message)

            # Step 4: Execution
            print(f"⚡ [Executing]: {action.description}...")
            result = self.planner.execute_action(action)

            # Step 5: Output & Speech
            if result.success:
                success_msg = f"Done! {result.message}"
                print(f"✅ {success_msg}")
                self.speaker.speak(success_msg)
            else:
                fail_msg = f"Failed to complete action: {result.message}"
                print(f"⚠️ {fail_msg}")
                self.speaker.speak(fail_msg)
                break

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
                    await self.process_user_command(text.strip())

            except (KeyboardInterrupt, asyncio.CancelledError):
                break
            except Exception as e:
                logger.error(f"Error in local processing loop: {e}")
                await asyncio.sleep(1)

    def shutdown(self):
        """Clean shutdown of all subsystems."""
        print("\n🛑 Shutting down Voice Agent gracefully...")
        self.running = False
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
