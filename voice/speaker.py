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

logger = logging.getLogger("VoiceAgent.Speaker")


class VoiceSpeaker:
    def __init__(self, rate: int = 0, volume: int = 100):
        # SAPI.SpVoice rate: -10 to +10 (0 is normal)
        # SAPI.SpVoice volume: 0 to 100
        self.rate = rate
        self.volume = volume
        self._speech_queue = queue.Queue()
        self._worker_thread = None
        self._running = False
        self._ready_event = threading.Event()
        self._backend = "none"

        self._start_worker()
        self._ready_event.wait(timeout=3.0)

    def _clean_text(self, text: str) -> str:
        """Sanitize text for TTS: strip URLs, markdown, emojis."""
        if not text:
            return ""
        clean = re.sub(r"https?://\S+", "link", text)
        clean = re.sub(r"[*_`#~]", "", clean)
        clean = clean.encode("ascii", "ignore").decode("ascii")
        clean = " ".join(clean.split())
        return clean.strip()

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
                sapi_voice.Rate = self.rate
                sapi_voice.Volume = self.volume
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
                pyttsx_engine.setProperty("rate", 175)
                pyttsx_engine.setProperty("volume", 1.0)
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

            clean = self._clean_text(item)
            if not clean:
                self._speech_queue.task_done()
                continue

            # Always print to console
            try:
                print(f"[Agent Speaks]: {clean}", flush=True)
            except Exception:
                pass

            # Speak via SAPI or pyttsx3
            if self._backend == "sapi" and sapi_voice:
                try:
                    sapi_voice.Speak(clean)
                except Exception as e:
                    logger.error(f"SAPI Speak error: {e}")
                    # Re-init SAPI voice if needed
                    try:
                        import pythoncom
                        import win32com.client
                        pythoncom.CoInitialize()
                        sapi_voice = win32com.client.Dispatch("SAPI.SpVoice")
                        sapi_voice.Rate = self.rate
                        sapi_voice.Volume = self.volume
                        sapi_voice.Speak(clean)
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
            self._speech_queue.put(text)

    def speak_sync(self, text: str):
        """Speak and block until finished speaking aloud."""
        if text:
            self._speech_queue.put(text)
            self._speech_queue.join()

    def speak_async(self, text: str):
        """Alias for speak()."""
        self.speak(text)

    def set_speed(self, rate: int = 0):
        self.rate = rate

    def stop(self):
        """Shutdown worker thread."""
        self._running = False
        self._speech_queue.put(None)
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3.0)
