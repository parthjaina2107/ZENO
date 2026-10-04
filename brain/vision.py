"""
ZENO Screen Vision Engine
Multimodal visual perception enabling ZENO to "see" and interpret the user's screen.
Utilizes Google Gemini 2.5 Flash multimodal vision with local screenshot capture.
"""

import io
import logging
import re
from typing import Optional, Dict, Any
from config import config
from .api_utils import call_gemini_with_fallback

logger = logging.getLogger("VoiceAgent.Vision")

VISION_PATTERNS = [
    r"look at (?:my|the) screen",
    r"what(?:'s| is) on (?:my|the) screen",
    r"read (?:my|the) screen",
    r"see (?:my|the) screen",
    r"explain (?:what(?:'s| is) on|the error on|this on) (?:my|the) screen",
    r"what error (?:is on|do you see on) (?:my|the) screen",
    r"summarize (?:my|the) screen",
    r"check (?:my|the) screen",
    r"inspect (?:my|the) screen",
    r"what am i looking at"
]


class ScreenVision:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        self.client = None
        self._init_client()

    def _init_client(self):
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info("ScreenVision: Gemini multimodal client initialized.")
            except Exception as e:
                logger.warning(f"ScreenVision: Could not initialize Gemini client: {e}")
                self.client = None
        else:
            logger.info("ScreenVision: No Gemini API key provided. Visual inspection will use fallback telemetry.")

    def is_vision_query(self, text: str) -> bool:
        """Determine if user utterance is asking about the screen."""
        lowered = text.lower().strip()
        for pattern in VISION_PATTERNS:
            if re.search(pattern, lowered):
                return True
        return False

    def capture_screen(self):
        """Capture the primary monitor as a PIL Image."""
        try:
            import pyautogui
            screenshot = pyautogui.screenshot()
            return screenshot
        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            return None

    def _get_active_window_title(self) -> str:
        """Attempt to retrieve the title of the currently focused window on Windows."""
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            return buff.value or "Desktop"
        except Exception:
            return "Active Application"

    async def analyze_screen(self, user_query: str, image=None) -> Dict[str, Any]:
        """
        Capture screen and use Gemini 2.5 Flash multimodal vision to answer the user's question.
        """
        # 1. Capture screen if not provided
        if image is None:
            image = self.capture_screen()

        if image is None:
            return {
                "success": False,
                "message": "I could not capture your screen right now. Please ensure your desktop is accessible.",
                "analysis": None
            }

        # 2. If Gemini client is active, run multimodal analysis
        if self.client:
            model_to_use = getattr(config, "GEMINI_MODEL", "gemini-2.5-flash")
            system_instruction = (
                "You are ZENO, an autonomous AI computer assistant. "
                "The user is asking you a question about their current computer screen. "
                "Carefully inspect the provided screenshot. "
                "Provide a concise, direct, helpful spoken response (2 to 4 sentences maximum) "
                "explaining what is on the screen, diagnosing any errors, or answering the user's specific question."
            )

            prompt = f"{system_instruction}\n\nUser Question: \"{user_query}\""

            try:
                # Resize if ultra high res to keep API latency low
                w, h = image.size
                if w > 1920:
                    ratio = 1920 / w
                    image = image.resize((1920, int(h * ratio)))

                response = await call_gemini_with_fallback(
                    client=self.client,
                    contents=[image, prompt],
                    primary_model=getattr(config, "GEMINI_MODEL", "gemini-2.5-flash"),
                )

                if response and hasattr(response, "text") and response.text:
                    analysis_text = response.text.strip()
                    if analysis_text:
                        return {
                            "success": True,
                            "message": analysis_text,
                            "analysis": analysis_text
                        }
            except Exception as e:
                logger.error(f"Gemini multimodal vision call failed: {e}")

        # 3. Fallback response if offline or API key missing
        active_window = self._get_active_window_title()
        w, h = image.size
        fallback_msg = (
            f"I took a look at your screen ({w} by {h} pixels). "
            f"Your active window appears to be '{active_window}'. "
            "For detailed visual intelligence, please configure your free Gemini API key in the environment."
        )
        return {
            "success": True,
            "message": fallback_msg,
            "analysis": fallback_msg
        }
