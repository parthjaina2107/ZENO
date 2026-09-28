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
from brain.nlu import NLUEngine
from brain.planner import ActionPlanner
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
        self.nlu = NLUEngine()
        self.executor = TaskExecutor()
        self.planner = ActionPlanner(executor=self.executor)
        self.permissions = PermissionManager(listener=self.listener, speaker=self.speaker)
        self.tunnel_manager = TunnelManager(port=self.port)
        self.server_thread = None

    def print_banner(self):
        banner = r"""
  __      __  _             ___                     _   
  \ \    / / (_)           /   \   __ _   ___  _ _  | |_ 
   \ \/\/ /  | |  _ _     / /_\ \ / _` | / -_)| ' \ |  _|
    \_/\_/   |_| (_)     /_/   \_\\__, | \___||_||_| \__|
                                  |___/                   
        """
        print(banner)
        print("=" * 64)
        print("  🎙️ VOICE AGENT — SECURE FULL-CONTROL AUTOMATION")
        print("=" * 64)
        print(f"  • Operating Mode     : {self.mode.upper()}")
        print(f"  • Microphone Ready   : {'YES' if self.listener.is_mic_available() else 'NO (Console Fallback)'}")
        print(f"  • Gemini AI Key      : {'Configured' if config.GEMINI_API_KEY else 'Missing (Local Rules Fallback)'}")
        print(f"  • Ngrok Auth Token   : {'Configured' if config.NGROK_AUTH_TOKEN else 'None (LAN Only)'}")
        print(f"  • Access Token       : {'*' * len(config.ACCESS_TOKEN)}")
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
        print(f"   Passphrase      : {config.ACCESS_TOKEN}\n")

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

        # Step 1: NLU understanding
        nlu_result = await self.nlu.understand(user_text)

        # Step 2: Planning
        actions = self.planner.plan(nlu_result)

        for i, action in enumerate(actions):
            if action.action_type in ("unhandled", "unknown"):
                msg = action.confirmation_message or "I could not understand that command."
                print(f"🤖 [Agent]: {msg}")
                self.speaker.speak(msg)
                return

            # Step 3: Permission Gate (only for actions requiring approval)
            if action.requires_permission:
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
        self.speaker.speak("Voice Agent is active and standing by.")
        print("\n🎧 Agent is listening. Speak clearly or type a command below.")
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
