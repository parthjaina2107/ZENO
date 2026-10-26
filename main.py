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
from voice.conversation import ConversationSession, interrupt_intent
from brain import ZenoBrain, ActionPlanner, NLUEngine
from brain.planner import describe_action
from brain.task_runner import TaskRunner
from brain.interaction import action_record, outcome_reply
from executor.task_executor import TaskExecutor
from logging.handlers import RotatingFileHandler
from executor.permissions import PermissionManager
from executor.agent_runner import AgentRunner, coordinator
from brain.planner import describe_action
from voice.listener import parse_confirmation
from awareness.service import AwarenessService
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
        self.awareness = AwarenessService() if config.AWARENESS_ENABLED else None
        self.brain.awareness = self.awareness
        self.planner = self.brain.planner
        self.nlu = self.brain.nlu
        self.permissions = PermissionManager(listener=self.listener, speaker=self.speaker)
        self.tunnel_manager = TunnelManager(port=self.port)
        self.server_thread = None
        self._local_approval = None
        self._local_task = None
        self.conversation = ConversationSession(config.WAKE_WORD_ENABLED, config.ASSISTANT_NAME,
                                                config.VOICE_FOLLOWUP_SECONDS)

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
        print(f"  • Proactive Updates  : {'Enabled — say brief me' if self.awareness else 'Disabled'}")
        print(f"  • Voice              : {config.TTS_VOICE if config.TTS_BACKEND == 'edge' else config.TTS_LOCAL_VOICE}")
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

        if brain_resp.kind == "task":
            async def progress(message):
                print(f"[Task] {message}")
            report = await TaskRunner(self.brain, self.permissions).run(
                brain_resp.message, self.approve_local_task, progress)
            print(report.summary())
            print(f"Task report: {report.report_path}")
            if getattr(self, 'awareness', None):
                self.awareness.record_task(report)
            self.speaker.speak(await outcome_reply(self.brain, user_text, report.steps, report.status, report.message))
            return

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


        # Step 2: OS Automation Action Execution
        actions = brain_resp.actions
        records = []
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
                    approved = await self.approve_local_task(action)
                    if not approved:
                        cancel_msg = f"Cancelled: '{action.description}' was not approved."
                        print(f"❌ {cancel_msg}")
                        self.speaker.speak(cancel_msg)
                        return
            else:
                self.permissions.log_decision(action, True, source="auto", reason="Routine action permitted by configured policy")

            # Step 4: Execution
            print(f"⚡ [Executing]: {action.description}...")
            result = await asyncio.to_thread(self.planner.execute_action, action)
            self.permissions.log_result(action, result, source="local")
            records.append(action_record(action, result))

            # Step 5: Output & Speech
            if result.success:
                success_msg = f"Done! {result.message}"
                print(f"✅ {success_msg}")
            else:
                fail_msg = f"Failed to complete action: {result.message}"
                print(f"⚠️ {fail_msg}")
                break
        if records:
            self.speaker.speak(await outcome_reply(self.brain, user_text, records))

    def voice_state(self, state):
        """Console microphone indicator; no audio or transcript is persisted here."""
        if getattr(self, '_voice_state', None) != state:
            self._voice_state = state
            print('[Voice: ' + state + ']', flush=True)

    async def wait_for_reply(self):
        """Optional headphone barge-in. Never execute commands heard during speech."""
        loop = asyncio.get_running_loop()
        if not config.VOICE_BARGE_IN or not self.listener.is_mic_available():
            self.voice_state('speaking — microphone paused')
            await loop.run_in_executor(None, self.speaker.wait_until_idle)
            return
        while self.running and self.speaker.is_busy:
            self.voice_state('speaking — interruption microphone active; headphones required')
            text = await loop.run_in_executor(None, self.listener.listen_once, 1, 3, True)
            if text and not self.listener.last_uncertain:
                intent = interrupt_intent(text, config.ASSISTANT_NAME)
                if intent:
                    self.speaker.interrupt()
                    await loop.run_in_executor(None, self.speaker.wait_until_idle)
                    if intent == 'correct':
                        self.brain.memory.add_turn('user', "That's not what I meant. Ask what should change; do not repeat or undo completed actions.")
                        print('[ZENO] Tell me what you would like changed. Completed actions have not been undone.')
                    self.conversation.extend()
                    return

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
        self._local_task = getattr(self, "_local_task", None)
        self._local_approval = getattr(self, "_local_approval", None)
        if (not getattr(self, 'text_mode', False) and self.conversation.wake_enabled
                and self.listener.is_mic_available()):
            self.voice_state('loading local wake recognition — microphone paused')
            if await asyncio.to_thread(self.listener._get_whisper_model) is None:
                print('Wake mode requires cached local speech recognition. Run --setup-speech, then retry, or use --text.')
                return
        self.speaker.speak(f"{config.ASSISTANT_NAME} is active and standing by.")
        print(f"\n🎧 {config.ASSISTANT_NAME} is listening. Speak clearly or type a command below.")
        print("   (Press Ctrl+C at any time to exit)\n")

        while self.running:
            try:
                # Listen for speech or console input
                loop = asyncio.get_running_loop()
                if getattr(self, "text_mode", False):
                    text = await loop.run_in_executor(None, input, "ZENO > ")
                else:
                    await self.wait_for_reply()
                    if getattr(self, 'awareness', None):
                        update = self.awareness.next_announcement()
                        if update:
                            print('[Briefing] ' + update)
                            self.speaker.speak(update)
                            await self.wait_for_reply()
                    await asyncio.sleep(0.2)
                    standby = self.conversation.wake_enabled and self.conversation.clock() >= self.conversation.active_until
                    self.voice_state('standby — microphone active for wake phrase' if standby else 'listening — microphone active')
                    text = await loop.run_in_executor(
                        None, self.listener.listen_once, config.LISTEN_TIMEOUT, config.PHRASE_TIMEOUT, standby)
                    # Console fallback is explicit user input, not ambient speech.
                    if text and self.listener.is_mic_available():
                        turn = self.conversation.accept(text, self.listener.last_uncertain)
                        if turn.kind == 'sleep' and await asyncio.to_thread(self.listener._get_whisper_model) is None:
                            self.conversation.wake_enabled = False
                            turn.message = 'Wake standby needs a cached local speech model. Run --setup-speech first; direct listening remains enabled.'
                        if turn.kind != 'command':
                            if turn.message:
                                print('[ZENO] ' + turn.message)
                                self.speaker.speak(turn.message)
                            continue
                        text = turn.text
                        if interrupt_intent(text, config.ASSISTANT_NAME) == 'correct':
                            self.brain.memory.add_turn('user', "That's not what I meant. Ask what should change; do not repeat or undo completed actions.")
                            self.speaker.speak('What would you like changed? Completed actions have not been undone.')
                            continue

                if text and text.strip():
                    text = text.strip()
                    clean = text.lower().strip(" .!?,")
                    if interrupt_intent(text, config.ASSISTANT_NAME) == "stop" or clean in ("stop", "cancel", "cancel everything", "abort", "halt", "kill", "emergency stop"):
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
        if self.awareness:
            self.awareness.stop()
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
        if self.awareness:
            self.awareness.start()

        # Start web server if mode is 'all' or 'server'
        if self.mode in ("all", "server"):
            self.start_web_server()

        if self.mode == "server":
            print("\n🚀 Server-only mode running. Access via web UI.")
            print("   Press Ctrl+C to stop.")
            try:
                while self.running:
                    import time
                    if self.awareness:
                        update = self.awareness.next_announcement()
                        if update:
                            self.speaker.speak(update)
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
    parser.add_argument("--text", action="store_true", help="Use console text input instead of the microphone")
    parser.add_argument('--briefing', action='store_true', help='Check sources and print a briefing without starting the microphone')
    parser.add_argument('--connect', choices=['gmail', 'outlook'], help='Connect a read-only inbox account')
    parser.add_argument('--credentials', help='Google Desktop OAuth client JSON file for --connect gmail')
    parser.add_argument('--voice-preview', action='store_true', help='Play the configured voice without starting the assistant')
    parser.add_argument('--voice', help='Neural voice name, for example en-IN-NeerjaNeural')
    parser.add_argument('--doctor', action='store_true', help='Check setup without recording or reading mail')
    parser.add_argument('--setup-speech', action='store_true', help='Download and validate the local faster-whisper model')
    parser.add_argument('--wake-word', action='store_true', help='Require Hey ZENO before opening a short voice conversation')
    parser.add_argument('--desktop', action='store_true', help='Open the native Windows press-to-talk app (no remote server)')
    args = parser.parse_args()

    if args.voice:
        config.TTS_VOICE = args.voice
    if args.desktop:
        try:
            from desktop.app import run_desktop
        except ImportError as exc:
            print('Desktop components are unavailable. Install requirements-desktop.txt, then retry. (' + type(exc).__name__ + ')')
            return 1
        return run_desktop()
    if args.doctor:
        from awareness.diagnostics import setup_report
        print(setup_report())
        return 0
    if args.setup_speech:
        print('Preparing local speech recognition. First setup downloads the model; this may take a few minutes.', flush=True)
        try:
            from voice.local_stt import load_model
            load_model(download=True)
        except Exception as exc:
            print('Speech setup failed (' + type(exc).__name__ + '). Install requirements-speech.txt and check your connection.')
            return 1
        print('Local speech model is ready. Start with --mode local --calibrate.')
        return 0
    if args.connect:
        from awareness.accounts import connect_account
        try:
            connect_account(args.connect, args.credentials)
        except Exception as exc:
            print(str(exc) if isinstance(exc, (ValueError, RuntimeError)) else 'Connection failed: ' + type(exc).__name__)
            return 1
        return 0
    if args.briefing:
        service = AwarenessService()
        service.poll()
        print(service.handle_command('connection status'))
        print(service.briefing())
        print(service.handle_command('work status'))
        return 0
    if args.voice_preview:
        speaker = VoiceSpeaker()
        speaker.speak_sync("Hi Parth. I'm Zeno. I'll keep an eye on your updates and let you focus on your work.")
        speaker.stop()
        return 0

    if args.wake_word:
        config.WAKE_WORD_ENABLED = True
    agent = VoiceAgentApp(mode=args.mode, port=args.port)
    agent.text_mode = args.text
    if args.text:
        agent.permissions.listener = None

    if args.calibrate:
        print("🎤 Calibrating microphone for ambient noise...")
        agent.listener.calibrate(duration=3.0)

    agent.run()


if __name__ == "__main__":
    sys.exit(main())
