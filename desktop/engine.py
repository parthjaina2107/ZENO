"""Desktop command pipeline. Reuses the existing brain, tools and permission policy."""
import asyncio

from brain.interaction import action_record, outcome_reply
from brain.planner import describe_action
from brain.task_runner import TaskRunner
from config import config


class DesktopEngine:
    def __init__(self):
        from brain import ZenoBrain
        from executor.task_executor import TaskExecutor
        from executor.permissions import PermissionManager
        from voice.listener import VoiceListener
        from voice.speaker import VoiceSpeaker
        from awareness.service import AwarenessService
        self.brain = ZenoBrain(executor=TaskExecutor())
        self.permissions = PermissionManager()
        self.speaker = VoiceSpeaker()
        # No ambient calibration or microphone access at startup.
        self.listener = VoiceListener(config.WHISPER_MODEL, initialize_microphone=False)
        self.awareness = AwarenessService() if config.AWARENESS_ENABLED else None
        self.brain.awareness = self.awareness
        if self.awareness:
            self.awareness.start()

    async def command(self, text, control, approve, emit):
        self.reasoning_unavailable = False
        from brain.coding_intent import CodingIntent
        from executor.coding_workspace import CodingRunner
        if not hasattr(self, 'coding_intent'):
            self.coding_intent = CodingIntent()
        from brain.companion import conversation_text, social_opening, CLEAR_REQUESTS
        routing_text = getattr(self.brain, 'strip_wake_prefix', lambda value: value)(text)
        if (conversation_text(routing_text) is not None or social_opening(routing_text)
                or routing_text.strip().lower().rstrip('.!?') in CLEAR_REQUESTS
                or routing_text.lower().startswith(('conversation style ', 'assistant profile '))
                or routing_text.lower().rstrip('.!?') in {'what can you do', 'show capabilities', 'help'}):
            self.coding_intent.pending_goal = ''
            coding = None
        else:
            coding = self.coding_intent.route(text)
        if coding:
            if coding.question:
                return coding.question
            try:
                runner = CodingRunner(self.permissions, self.brain.planner.executor.file)
                reply = await runner.run(coding, approve, emit, control)
                if runner.needs_clarification:
                    self.coding_intent.pending_goal = coding.goal
                return reply
            except (ValueError, RuntimeError, OSError) as exc:
                return 'Coding task could not start: ' + str(exc)
        emit("state", "Thinking")
        response = await control.wait(self.brain.think(text))
        control.check()
        if getattr(response, 'data', None) and response.data.get('service_error'):
            self.reasoning_unavailable = True
            emit('service_error', response.data['service_error'])
        if response.kind == "task":
            async def progress(message):
                control.check()
                emit("state", "Working")
                emit("detail", message)
            report = await TaskRunner(self.brain, self.permissions).run(
                response.message, approve, progress, control=control)
            control.check()
            if self.awareness:
                self.awareness.record_task(report)
            emit("detail", report.summary())
            reply = await control.wait(outcome_reply(self.brain, text, report.steps, report.status, report.message))
        elif response.kind in {"chat", "vision", "memory", "abort"}:
            reply = response.message
        else:
            records = []
            for action in response.actions:
                control.check()
                if action.action_type in {"unknown", "unhandled"}:
                    return action.confirmation_message or "Please rephrase that request."
                if action.requires_permission:
                    if not await control.wait(approve(action)):
                        return "Cancelled. No further actions will run."
                else:
                    self.permissions.log_decision(action, True, source="desktop", reason="Routine action permitted by configured policy")
                control.check()
                emit("state", "Working")
                emit("detail", describe_action(action))
                result = await control.call(self.brain.planner.execute_action, action)
                self.permissions.log_result(action, result, source="desktop")
                records.append(action_record(action, result))
                control.check()
                emit("detail", result.message)
                if not result.success:
                    break
            reply = await control.wait(outcome_reply(self.brain, text, records))
        control.check()
        return reply

    async def run(self, text, control, approve, emit, settings):
        if text is None:
            from .audio import capture
            emit("state", "Opening microphone")
            def microphone_opened():
                emit('microphone', 'on')
                emit('state', 'Listening')
            # Load only the configured recognizer while the user speaks. Both
            # workers drain on cancellation; the microphone still opens on demand.
            audio, _ = await asyncio.gather(
                control.call(capture, control, settings.microphone,
                             pause_seconds=settings.pause_seconds,
                             on_open=microphone_opened,
                             on_close=lambda: emit('microphone', 'off'),
                             on_level=lambda level: emit("level", str(level))),
                control.call(self.listener._get_whisper_model),
            )
            control.check()
            if audio is None:
                return "I didn't hear a command. Press your shortcut to try again."
            emit("state", "Transcribing")
            # Keep this serial: a cancelled recognizer must finish before it is reused.
            text = await control.call(self.listener._transcribe_audio, audio)
            control.check()
            if not text:
                return "I couldn't understand the audio. Try again or type your request."
            emit("transcript", text)
            if self.listener.last_uncertain:
                emit("draft", text)
                return "I'm not confident I heard that correctly. Review the text below and send it, or try again."
        else:
            emit("transcript", text)
        if getattr(control, 'chat_only', False):
            text = 'Chat: ' + text
        reply = await self.command(text, control, approve, emit)
        control.check()
        emit("reply", reply)
        if settings.spoken_replies and not getattr(self, 'reasoning_unavailable', False):
            emit("state", "Speaking")
            control.immediate(self.speaker.speak, reply)
            while self.speaker.is_busy:
                if control.cancelled.is_set():
                    self.speaker.interrupt()
                await asyncio.sleep(0.05)
            control.check()
        return None

    def close(self):
        if self.awareness:
            self.awareness.stop()
        self.listener.stop()
        self.speaker.stop()
