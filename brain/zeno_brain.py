"""
ZENO Cognitive Brain
The unified intelligence core of ZENO:
- Persona & Identity Management
- Contextual Dialogue & Short-Term Memory
- Persistent Long-Term Memory (Facts, Preferences, Aliases)
- Multimodal Screen Vision Perception
- Natural Language Understanding & OS Action Planning
- General Conversational Reasoning & Q&A
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from config import config
from .nlu import NLUEngine
from .planner import ActionPlanner, PlannedAction
from .memory import ZenoMemory
from .vision import ScreenVision
from .api_utils import call_gemini_with_fallback

logger = logging.getLogger("VoiceAgent.ZenoBrain")


@dataclass
class BrainResponse:
    kind: str  # "action", "chat", "vision", "memory"
    message: str
    actions: List[PlannedAction] = field(default_factory=list)
    data: Optional[Dict[str, Any]] = None


class ZenoBrain:
    def __init__(self, api_key: Optional[str] = None, executor=None):
        self.api_key = api_key or config.GEMINI_API_KEY
        self.assistant_name = config.ASSISTANT_NAME  # "ZENO"
        self.memory = ZenoMemory()
        self.vision = ScreenVision(api_key=self.api_key)
        self.nlu = NLUEngine(api_key=self.api_key)
        self.planner = ActionPlanner(executor=executor)
        self.client = None
        self._init_chat_client()

    def _init_chat_client(self):
        """Initialize Google GenAI client for conversational chat & reasoning."""
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"{self.assistant_name} Conversational Chat client initialized.")
            except Exception as e:
                logger.warning(f"Could not initialize GenAI chat client: {e}")
                self.client = None

    def strip_wake_prefix(self, text: str) -> str:
        """Strip conversational address prefixes like 'Hey Zeno', 'Zeno,', 'OK Zeno'."""
        name = re.escape(self.assistant_name)
        pattern = rf"^(?:hey\s+|hi\s+|hello\s+|ok\s+|okay\s+)?{name}[,\s:]*\s*"
        cleaned = re.sub(pattern, "", text.strip(), flags=re.IGNORECASE)
        return cleaned.strip() if cleaned.strip() else text.strip()

    async def _generate_conversational_reply(self, user_text: str) -> str:
        """Generate conversational answer using Gemini 2.5 Flash with memory & context."""
        if self.client:
            model_to_use = getattr(config, "GEMINI_MODEL", "gemini-3.8-flash")
            dialogue_context = self.memory.format_dialogue_context(limit=4)
            personal_memories = self.memory.format_memory_for_prompt()

            system_instruction = (
                f"You are {self.assistant_name}, a highly intelligent, polite, and capable personal AI desktop assistant. "
                "Your responses are spoken aloud via Text-to-Speech or sent to the user's mobile screen. "
                "Keep spoken answers natural, clear, and concise (1 to 3 sentences) unless the user specifically asks for in-depth details. "
                "Always maintain your identity as ZENO."
            )

            prompt_parts = [system_instruction]
            if personal_memories:
                prompt_parts.append(personal_memories)
            if dialogue_context:
                prompt_parts.append(f"Recent Conversation:\n{dialogue_context}")
            prompt_parts.append(f"User: {user_text}\n{self.assistant_name}:")

            full_prompt = "\n\n".join(prompt_parts)

            try:
                response = await call_gemini_with_fallback(
                    client=self.client,
                    contents=full_prompt,
                    primary_model=getattr(config, "GEMINI_MODEL", "gemini-3.8-flash"),
                )
                if response and hasattr(response, "text") and response.text:
                    answer = response.text.strip()
                    if answer:
                        return answer
            except Exception as e:
                logger.error(f"Conversational generation error: {e}")

        # Local fallback if offline or API key missing
        return (
            f"I am {self.assistant_name}, standing by. I can run system commands, control apps, "
            f"adjust volume, take screenshots, or check your battery. "
            f"To unlock full conversational Q&A and screen vision, please configure your Gemini API key."
        )

    async def think(self, raw_user_text: str) -> BrainResponse:
        """
        Master cognitive decision pipeline:
        1. Parse persona / wake word
        2. Check memory commands (remember, recall, forget)
        3. Check vision commands (look at screen, what's on screen)
        4. Check OS automation actions (NLU -> Planner)
        5. Fallback to conversational Q&A & reasoning (Gemini Chat)
        """
        raw_text = raw_user_text.strip()
        if not raw_text:
            return BrainResponse(
                kind="chat",
                message="I didn't hear anything. Please speak or type your command."
            )

        clean_text = self.strip_wake_prefix(raw_text)
        lowered = clean_text.lower().strip(".!?,")

        # ----------------------------------------------------------------------
        # 0. Emergency Stop / Abort intent (Pre-NLU kill switch)
        # ----------------------------------------------------------------------
        if lowered in ("stop", "cancel", "cancel everything", "abort", "halt", "kill", "emergency stop"):
            reply = "Emergency stop acknowledged. Stopping all actions."
            self.memory.add_turn("user", clean_text)
            self.memory.add_turn("zeno", reply)
            return BrainResponse(kind="abort", message=reply)

        # ----------------------------------------------------------------------
        # 1. Identity / Greeting queries
        # ----------------------------------------------------------------------
        if lowered in ("who are you", "what is your name", "who are you?", "what's your name"):
            reply = f"I am {self.assistant_name}, your autonomous voice and remote automation assistant."
            self.memory.add_turn("user", clean_text)
            self.memory.add_turn("zeno", reply)
            return BrainResponse(kind="chat", message=reply)


        # ----------------------------------------------------------------------
        # 2. Long-term memory intent
        # ----------------------------------------------------------------------
        memory_intent = self.memory.parse_memory_intent(clean_text)
        if memory_intent:
            reply_msg = memory_intent.get("message", "Memory updated.")
            self.memory.add_turn("user", clean_text)
            self.memory.add_turn("zeno", reply_msg)
            return BrainResponse(kind="memory", message=reply_msg, data=memory_intent)

        # ----------------------------------------------------------------------
        # 3. Screen Vision intent
        # ----------------------------------------------------------------------
        if self.vision.is_vision_query(clean_text):
            vision_result = await self.vision.analyze_screen(clean_text)
            reply_msg = vision_result.get("message", "Screen inspection complete.")
            self.memory.add_turn("user", clean_text)
            self.memory.add_turn("zeno", reply_msg)
            return BrainResponse(kind="vision", message=reply_msg, data=vision_result)

        # ----------------------------------------------------------------------
        # 4. OS Automation Action intent
        # ----------------------------------------------------------------------
        nlu_result = await self.nlu.understand(clean_text)
        action_type = nlu_result.get("action", "unknown")

        if nlu_result.get("understood", False) and action_type not in ("unknown", "unhandled", "none"):
            # Legitimate OS Action
            actions = self.planner.plan(nlu_result)
            confirm_msg = nlu_result.get("confirmation_message") or f"Planning action: {nlu_result.get('description', '')}"
            self.memory.add_turn("user", clean_text)
            self.memory.add_turn("zeno", confirm_msg)
            return BrainResponse(
                kind="action",
                message=confirm_msg,
                actions=actions,
                data=nlu_result
            )

        # ----------------------------------------------------------------------
        # 5. Conversational Reasoning / Q&A Fallback
        # ----------------------------------------------------------------------
        chat_reply = await self._generate_conversational_reply(clean_text)
        self.memory.add_turn("user", clean_text)
        self.memory.add_turn("zeno", chat_reply)
        return BrainResponse(kind="chat", message=chat_reply)
