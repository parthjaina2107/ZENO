"""
Voice Listener (Speech-to-Text) supporting microphone capture,
energy threshold calibration, speech recognition with graceful fallback,
and confirmation parsing.
"""

import logging
import threading
import time
from typing import Optional, Callable

logger = logging.getLogger("VoiceAgent.Listener")

APPROVE_WORDS = {
    "yes", "yeah", "yep", "approve", "approved", "do it", "go ahead",
    "proceed", "confirm", "confirmed", "ok", "okay", "sure", "execute", "accept"
}

DENY_WORDS = {
    "no", "nope", "cancel", "cancelled", "stop", "don't", "dont", "deny",
    "denied", "abort", "never", "negative", "reject"
}


class VoiceListener:
    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self._recognizer = None
        self._microphone = None
        self._whisper_model = None
        self._running = False
        self._thread = None
        self._mic_available = False

        self._init_speech_recognition()

    def _init_speech_recognition(self):
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._recognizer.dynamic_energy_threshold = True
            self._recognizer.pause_threshold = 0.8
            
            # Check for microphone
            try:
                self._microphone = sr.Microphone()
                # Test microphone access
                with self._microphone as source:
                    self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
                self._mic_available = True
                logger.info("Microphone initialized and calibrated successfully.")
            except Exception as e:
                logger.warning(f"No working microphone detected: {e}. VoiceListener will offer console/text input.")
                self._mic_available = False
                self._microphone = None
        except Exception as e:
            logger.error(f"Failed to import or initialize speech_recognition: {e}")
            self._mic_available = False

    def is_mic_available(self) -> bool:
        return self._mic_available

    def calibrate(self, duration: float = 2.0):
        """Listen to ambient noise to set energy threshold."""
        if not self._mic_available or not self._microphone:
            return
        try:
            import speech_recognition as sr
            with self._microphone as source:
                logger.info(f"Calibrating ambient noise for {duration} seconds...")
                self._recognizer.adjust_for_ambient_noise(source, duration=duration)
                logger.info(f"Calibration complete. Energy threshold: {self._recognizer.energy_threshold}")
        except Exception as e:
            logger.warning(f"Calibration failed: {e}")

    def _transcribe_audio(self, audio_data) -> Optional[str]:
        """Transcribe captured audio using SpeechRecognition or Whisper."""
        # 1. Try local whisper if loaded
        if self._whisper_model is not None:
            try:
                import io
                import tempfile
                import os
                wav_bytes = audio_data.get_wav_data()
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(wav_bytes)
                    tmp_name = f.name
                try:
                    result = self._whisper_model.transcribe(tmp_name)
                    text = result.get("text", "").strip()
                    return text if text else None
                finally:
                    if os.path.exists(tmp_name):
                        os.remove(tmp_name)
            except Exception as e:
                logger.warning(f"Whisper transcription failed, falling back: {e}")

        # 2. Try SpeechRecognition's Google STT (free, high quality, requires internet)
        try:
            text = self._recognizer.recognize_google(audio_data)
            return text.strip()
        except Exception:
            # Silence or uncomprehended speech
            return None

    def listen_once(self, timeout: int = 5, phrase_time_limit: int = 10) -> Optional[str]:
        """Listen for one phrase, return text or None if silence/error."""
        if not self._mic_available or not self._microphone:
            # Fall back to console input if no microphone
            try:
                print("🎤 [Local Mic Not Available - Type command or press Enter]: ", end="", flush=True)
                # Read line with quick return
                import sys
                line = sys.stdin.readline()
                return line.strip() if line and line.strip() else None
            except Exception:
                return None

        import speech_recognition as sr
        try:
            with self._microphone as source:
                logger.debug("Listening for audio...")
                audio = self._recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
                text = self._transcribe_audio(audio)
                if text:
                    logger.info(f"Heard speech: {text}")
                return text
        except sr.WaitTimeoutError:
            return None
        except Exception as e:
            logger.debug(f"Audio capture issue: {e}")
            return None

    def listen_for_confirmation(self, timeout: int = 15) -> Optional[bool]:
        """
        Listen specifically for approval or denial.
        Returns:
            True: if approved
            False: if denied
            None: if timeout or unclear
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            remaining = int(timeout - (time.time() - start_time))
            if remaining <= 0:
                break
            text = self.listen_once(timeout=min(5, remaining), phrase_time_limit=4)
            if not text:
                continue

            cleaned = text.lower().strip()
            words = set(cleaned.split())

            # Check approve
            if any(word in APPROVE_WORDS for word in words) or cleaned in APPROVE_WORDS:
                return True
            # Check deny
            if any(word in DENY_WORDS for word in words) or cleaned in DENY_WORDS:
                return False

        return None

    def start_continuous(self, callback: Callable[[str], None], timeout: int = 5):
        """Start background thread that calls callback(text) on each detected phrase."""
        if self._running:
            return

        self._running = True

        def loop():
            logger.info("Continuous voice listening started.")
            while self._running:
                text = self.listen_once(timeout=timeout)
                if text and self._running:
                    callback(text)

        self._thread = threading.Thread(target=loop, daemon=True, name="Listener-Thread")
        self._thread.start()

    def stop(self):
        """Stop listening and clean up resources."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("VoiceListener stopped.")
