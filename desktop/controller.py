"""Qt-to-worker boundary: one request at a time, no UI work on worker threads."""
import asyncio
from dataclasses import replace
import logging
import threading
import time
import uuid

from PySide6.QtCore import QObject, Signal, Slot

from brain.planner import describe_action
from .control import RunControl
from .engine import DesktopEngine


class DesktopController(QObject):
    event = Signal(str, str)
    approval = Signal(str, str)
    finished = Signal()
    idle = Signal()

    def __init__(self, settings, engine_factory=DesktopEngine):
        super().__init__()
        self.settings = settings
        self.engine_factory = engine_factory
        self.engine = None
        self.control = None
        self.busy = False
        self.pending_id = None
        self.answer = None
        self.answer_lock = threading.Lock()
        self.finished.connect(self._finished)

    def activate(self, text=None):
        if self.busy:
            self.stop()
            return
        self.busy = True
        self.control = RunControl()
        settings = replace(self.settings)
        self.event.emit("state", "Preparing")
        threading.Thread(target=self._work, args=(text, self.control, settings),
                         daemon=True, name="Zeno-Desktop-Request").start()

    def stop(self):
        if self.busy:
            self.control.cancel()
            if self.engine:
                self.engine.speaker.interrupt()
            self.event.emit("state", "Stopping")
            self.event.emit("detail", "Stopping remaining steps. An action already started may finish; completed changes are not undone.")

    def answer_approval(self, request_id, approved):
        with self.answer_lock:
            if request_id == self.pending_id and not self.control.cancelled.is_set():
                self.answer = bool(approved)

    async def _approve(self, action, control):
        approved = False
        try:
            # Preserve the existing high-risk double confirmation, without voice/input().
            for stage in range(2 if action.risk_level == "high" else 1):
                control.check()
                request_id = uuid.uuid4().hex
                with self.answer_lock:
                    self.pending_id, self.answer = request_id, None
                self.event.emit("state", "Approval needed")
                prompt = describe_action(action)
                if stage:
                    prompt = "Final confirmation — this is a high-risk action.\n" + prompt
                self.approval.emit(request_id, prompt)
                deadline = time.monotonic() + 60
                answer = None
                while time.monotonic() < deadline:
                    control.check()
                    with self.answer_lock:
                        answer = self.answer
                    if answer is not None:
                        break
                    await asyncio.sleep(0.05)
                if answer is not True:
                    return False
            control.check()
            approved = True
            return True
        finally:
            with self.answer_lock:
                self.pending_id, self.answer = None, None
            self.approval.emit("", "")
            self.engine.permissions.log_decision(action, approved, source="desktop")

    def _work(self, text, control, settings):
        stage, began = "Preparing", time.monotonic()
        def emit(kind, value):
            nonlocal stage, began
            if not control.cancelled.is_set():
                if kind == "state":
                    now = time.monotonic()
                    logging.getLogger("VoiceAgent.Desktop.Latency").info(
                        "%s took %.3fs", stage, now - began)
                    stage, began = value, now
                self.event.emit(kind, value)
        try:
            if self.engine is None:
                self.engine = self.engine_factory()
            control.check()
            async def run():
                return await self.engine.run(text, control, lambda action: self._approve(action, control), emit, settings)
            # asyncio.run drains worker calls before the UI allows another request.
            reply = asyncio.run(run())
            control.check()
            if reply:
                emit("reply", reply)
        except asyncio.CancelledError:
            self.event.emit("detail", "No remaining steps will run. Any already-started operation has been allowed to finish.")
            self.event.emit("reply", "Stopped. Completed actions have not been undone.")
        except Exception as exc:
            logging.getLogger("VoiceAgent.Desktop").exception("Desktop request failed")
            self.event.emit("reply", "Something went wrong (" + type(exc).__name__ + "). Check your microphone and connection, then try again. Details are in the local log.")
        finally:
            logging.getLogger("VoiceAgent.Desktop.Latency").info(
                "%s took %.3fs", stage, time.monotonic() - began)
            self.finished.emit()

    @Slot()
    def _finished(self):
        self.busy = False
        self.control = None
        self.event.emit("state", "Ready")
        self.idle.emit()
