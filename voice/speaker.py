"""
Voice Speaker (Text-to-Speech)
Uses Windows native SAPI.SpVoice (via win32com) for 100% reliable hardware audio on Windows,
with pyttsx3 fallback for cross-platform support, and console fallback.
"""

import queue
import re
import sys
import threading
import time
import logging
import unicodedata
from config import config

logger = logging.getLogger("VoiceAgent.Speaker")


class VoiceSpeaker:
    def __init__(self, rate: int = -1, volume: int = 80):
        # SAPI.SpVoice rate: -10 to +10 (0 is normal)
        # SAPI.SpVoice volume: 0 to 100
        self.rate = rate
        self.volume = volume
        self._speech_queue = queue.Queue()
        self._worker_thread = None
        self._running = False
        self._ready_event = threading.Event()
        self._backend = "none"
        self.speech_generation = 0
        self._neural_retry_at = 0.0
        self._generation = 0
        self._queue_lock = threading.Lock()

        self._start_worker()
        self._ready_event.wait(timeout=3.0)

    def _clean_text(self, text: str) -> str:
        """Sanitize text for TTS: strip URLs, markdown, emojis."""
        if not text:
            return ""
        clean = re.sub(r"https?://\S+", "link", text)
        clean = re.sub(r"[*_`#~]", "", clean)
        clean = ''.join(c for c in clean if unicodedata.category(c) not in ('So', 'Cs', 'Cf'))
        clean = " ".join(clean.split())
        return clean.strip()

    def _configure_sapi(self, voice):
        for token in voice.GetVoices():
            if config.TTS_LOCAL_VOICE.lower() in token.GetDescription().lower():
                voice.Voice = token
                break
        voice.Rate = self.rate
        voice.Volume = self.volume

    def _worker_loop(self):
        """Worker thread: manages speech dispatch."""
        sapi_voice = None
        pyttsx_engine = None

        # 1. On Windows, try native SAPI.SpVoice first (most reliable, no thread lock)
        if sys.platform == "win32":
            try:
                import pythoncom
                import win32com.client
                pythoncom.CoInitialize()
                sapi_voice = win32com.client.Dispatch("SAPI.SpVoice")
                self._configure_sapi(sapi_voice)
                self._backend = "sapi"
                logger.info("VoiceSpeaker initialized using native Windows SAPI.SpVoice.")
            except Exception as e:
                logger.warning(f"SAPI init failed: {e}, attempting pyttsx3 fallback.")
                sapi_voice = None

        # 2. Try pyttsx3 if SAPI is not available
        if sapi_voice is None:
            try:
                import pyttsx3
                pyttsx_engine = pyttsx3.init()
                pyttsx_engine.setProperty("rate", 155)
                pyttsx_engine.setProperty("volume", self.volume / 100)
                for voice in pyttsx_engine.getProperty("voices"):
                    if config.TTS_LOCAL_VOICE.lower() in voice.name.lower():
                        pyttsx_engine.setProperty("voice", voice.id)
                        break
                self._backend = "pyttsx3"
                logger.info("VoiceSpeaker initialized using pyttsx3.")
            except Exception as e:
                logger.warning(f"pyttsx3 init failed: {e}. Voice output disabled.")
                self._backend = "console"

        self._ready_event.set()

        while self._running:
            try:
                item = self._speech_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if item is None:
                self._speech_queue.task_done()
                break

            generation, text = item
            if generation != self._generation:
                self._speech_queue.task_done()
                continue
            clean = self._clean_text(text)
            if not clean:
                self._speech_queue.task_done()
                continue

            # Always print to console
            try:
                print(f"[Agent Speaks]: {clean}", flush=True)
            except Exception:
                pass

            # Neural speech is optional; a network failure falls back to local speech.
            if config.TTS_BACKEND == "edge" and time.monotonic() >= self._neural_retry_at:
                try:
                    from .neural import speak_neural
                    speak_neural(clean, lambda: self._running and generation == self._generation)
                    self._speech_queue.task_done()
                    continue
                except Exception as exc:
                    logger.warning("Neural speech unavailable (%s); using local voice for five minutes.", type(exc).__name__)
                    self._neural_retry_at = time.monotonic() + 300

            if generation != self._generation:
                self._speech_queue.task_done()
                continue

            # Speak via SAPI or pyttsx3
            if self._backend == "sapi" and sapi_voice:
                try:
                    sapi_voice.Speak(clean, 1)  # Async: cancellation is handled on this COM thread.
                    while self._running and generation == self._generation:
                        if sapi_voice.WaitUntilDone(50):
                            break
                    if not self._running or generation != self._generation:
                        sapi_voice.Speak('', 3)  # Purge pending speech.
                except Exception as e:
                    logger.error(f"SAPI Speak error: {e}")
                    # Re-init SAPI voice if needed
                    try:
                        import pythoncom
                        import win32com.client
                        pythoncom.CoInitialize()
                        sapi_voice = win32com.client.Dispatch("SAPI.SpVoice")
                        self._configure_sapi(sapi_voice)
                        # Do not replay a partially spoken reply after a backend failure.
                    except Exception as e2:
                        logger.error(f"SAPI re-init failed: {e2}")

            elif self._backend == "pyttsx3" and pyttsx_engine:
                try:
                    pyttsx_engine.say(clean)
                    pyttsx_engine.runAndWait()
                except Exception as e:
                    logger.error(f"pyttsx3 Speak error: {e}")

            self._speech_queue.task_done()

        # Cleanup COM on exit
        if sys.platform == "win32":
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass

    def _start_worker(self):
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop, daemon=True, name="TTS-Worker"
        )
        self._worker_thread.start()

    def speak(self, text: str):
        """Queue text to be spoken aloud asynchronously."""
        if text:
            self.speech_generation = getattr(self, "speech_generation", 0) + 1
            with self._queue_lock:
                self._speech_queue.put((self._generation, text))

    def speech_state(self):
        """A capture spanning any TTS utterance must not be treated as a user command."""
        return self.speech_generation, self._speech_queue.unfinished_tasks > 0

    def speak_sync(self, text: str):
        """Speak and block until finished speaking aloud."""
        if text:
            self.speak(text)
            self._speech_queue.join()

    @property
    def is_busy(self):
        return self._speech_queue.unfinished_tasks > 0

    def interrupt(self):
        """Cancel this generation and queued replies, without shutting down the speaker."""
        with self._queue_lock:
            self._generation += 1
            while True:
                try:
                    item = self._speech_queue.get_nowait()
                except queue.Empty:
                    break
                self._speech_queue.task_done()
                if item is None:
                    self._speech_queue.put(None)
                    break

    def speak_async(self, text: str):
        """Alias for speak()."""
        self.speak(text)

    def wait_until_idle(self):
        """Allow microphone capture only after queued speech has finished."""
        self._speech_queue.join()

    def set_speed(self, rate: int = 0):
        self.rate = rate

    def stop(self):
        """Shutdown worker thread."""
        self._running = False
        self.interrupt()
        self._speech_queue.put(None)
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3.0)
