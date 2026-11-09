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
from .api_utils import cloud_allowed, reasoning_available, call_gemini_with_fallback, last_api_failure, reasoning_failure_message
from .agent import GoalPlanner
from .interaction import is_direct_command, route_request

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
        self.goal_planner = GoalPlanner(self.nlu, self.planner)
        self.client = None
        self.awaiting_clarification = False
        self.pending_folder_location = None
        self.gmail_mailbox = None
        self.awareness = None
        self._init_chat_client()

    def _init_chat_client(self):
        """Initialize Google GenAI client for conversational chat & reasoning."""
        if self.api_key and cloud_allowed():
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key, vertexai=False, enterprise=False,
                                           http_options={'base_url': 'https://generativelanguage.googleapis.com'})
                logger.info(f"{self.assistant_name} Conversational Chat client initialized.")
            except Exception as e:
                logger.warning(f"Could not initialize GenAI chat client: {e}")
                self.client = None

    def strip_wake_prefix(self, text: str) -> str:
        """Strip conversational address prefixes like 'Hey Zeno', 'Zeno,', 'OK Zeno'."""
        name = re.escape(self.assistant_name)
        pattern = rf"^(?:hey\s+|hi\s+|hello\s+|ok\s+|okay\s+)?{name}\b[,\s:]*\s*"
        if name.lower() == "zeno":
            text = re.sub(r"^((?:hey|hi|hello|okay|ok)\s+)xeno\b", r"\1Zeno", text, flags=re.I)
        cleaned = re.sub(pattern, "", text.strip(), flags=re.IGNORECASE)
        return cleaned.strip() if cleaned.strip() else text.strip()

    async def _generate_conversational_reply(self, user_text: str) -> str:
        """Tool-free companion generation with bounded provider calls."""
        from .companion import context, instructions, offline_reply
        self.conversation_unavailable = False
        if reasoning_available(self.client):
            try:
                response = await call_gemini_with_fallback(
                    client=self.client,
                    contents=context(self.memory, user_text),
                    generation_config={'system_instruction': instructions(self.memory, chat_only=True)},
                    max_retries=1,
                )
                if response and isinstance(response.text, str) and response.text.strip():
                    return response.text.strip()
            except Exception:
                logger.warning('Companion generation unavailable')
        self.conversation_unavailable = True
        return offline_reply(user_text)

    async def think(self, raw_user_text: str, agent_mode: bool = False) -> BrainResponse:
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
        clean_text = re.sub(r"^(?:(?:can|could|would) you |please )+", "", clean_text, flags=re.I)
        lowered = clean_text.lower().strip(".!?,")

        from .companion import conversation_text, social_opening, CLEAR_REQUESTS, STYLES, PROFILES
        chat_text = conversation_text(clean_text)
        if lowered in CLEAR_REQUESTS or (chat_text is not None and chat_text.lower().rstrip('.!?') in CLEAR_REQUESTS):
            self.gmail_mailbox = None
            self.pending_folder_location = None
            self.memory.clear_short_term()
            self.awaiting_clarification = False
            return BrainResponse(kind='chat', message='Cleared the conversation context for this session. Saved facts and copies in the interface or provider are unchanged.')
        style_match = re.fullmatch(r'conversation style\s+(\w+)', lowered)
        if style_match and chat_text is None:
            style = style_match.group(1)
            if style not in STYLES:
                return BrainResponse(kind='chat', message='Choose balanced, gentle, playful or direct.')
            self.memory.remember_fact('conversation_style', style, category='user_preferences')
            return BrainResponse(kind='memory', message=f'Conversation style set to {style}.')
        profile_match = re.fullmatch(r'assistant profile\s+(\w+)', lowered)
        if profile_match and chat_text is None:
            profile = profile_match.group(1)
            if profile not in PROFILES:
                return BrainResponse(kind='chat', message='Choose balanced, focused or warm.')
            self.memory.remember_fact('assistant_profile', profile, category='user_preferences')
            return BrainResponse(kind='memory', message=f'Assistant profile set to {profile}.')
        if chat_text is None and lowered in {'what can you do', 'show capabilities', 'help'}:
            return BrainResponse(kind='chat', message=(
                'We can talk, explore ideas, or work through a problem. I can also run supported '
                'computer tasks, such as opening apps, checking system status and working with permitted files. '
                'The native desktop has a coding-workspace mode when its external Codex service is enabled, installed and signed in. '
                'Choose Just talk for conversation only, or ask for an Agent task. Sensitive steps need your approval.'))
        if chat_text is None and social_opening(clean_text):
            chat_text = clean_text
        if chat_text is not None:
            if self.gmail_mailbox:
                self.gmail_mailbox.composing = None
            self.pending_folder_location = None
            self.awaiting_clarification = False
            reply = await self._generate_conversational_reply(chat_text)
            self.memory.add_turn('user', chat_text)
            self.memory.add_turn('zeno', reply)
            return BrainResponse(kind='chat', message=reply,
                                 data={'conversation_only': True, 'service_error': 'unavailable'}
                                 if self.conversation_unavailable else {'conversation_only': True})

        tool_text = re.sub(r"^(?:task|agent(?: task)?)\s*:\s*", "", clean_text, flags=re.I)
        from awareness.gmail import mail_request
        from .folder_intent import folder_request
        from .nlu import excludes_execution, split_commands
        if any(excludes_execution(part) for part in split_commands(tool_text)) and re.match(
                r"^(?:open|launch|create|make|close|set|run|restart|shutdown)\b", tool_text, re.I):
            return BrainResponse(kind='chat', message='No actions were run. Please give the intended command without the conflicting condition.')
        parts = re.split(r"\s+(?:and then|then|and)\s+", tool_text, maxsplit=1, flags=re.I)
        if len(parts) == 2 and (folder := folder_request(parts[0])) and folder['name']:
            following = mail_request(parts[1])
            if following and following[0] in {"collect", "draft", "write"}:
                first = await self.think(parts[0], agent_mode=agent_mode or tool_text != clean_text)
                if first.kind == 'action':
                    first.data['following_mail'] = following
                return first
        if self.vision.is_vision_query(tool_text):
            if self.gmail_mailbox:
                self.gmail_mailbox.composing = None
            result = await self.vision.analyze_screen(tool_text)
            return BrainResponse(kind="vision", message=result["message"], data=result)

        request = mail_request(tool_text)
        if request is None and self.gmail_mailbox is not None:
            request = self.gmail_mailbox.followup(tool_text)
        if request is not None:
            self.pending_folder_location = None
            self.awaiting_clarification = False
            reply = await self.respond_to_mail(request)
            return BrainResponse(kind="chat", message=reply, data={"mail_read_only": request[0] in {"read", "search"},
                                "review_send": request[0] == "review_send" and bool(self.gmail_mailbox.pending)})

        if self.awareness is not None:
            import asyncio
            from awareness.commands import normalize, SUMMARY_REQUESTS
            if normalize(clean_text) in SUMMARY_REQUESTS:
                return BrainResponse(kind='chat', message=await self.awareness.summarize(self.client))
            briefing = await asyncio.to_thread(self.awareness.handle_command, clean_text)
            if briefing is not None:
                # Do not inject notification contents into the action planner's history.
                return BrainResponse(kind="chat", message=briefing)

        # ----------------------------------------------------------------------
        # 0. Emergency Stop / Abort intent (Pre-NLU kill switch)
        # ----------------------------------------------------------------------
        if lowered in ("stop", "cancel", "cancel everything", "abort", "halt", "kill", "emergency stop"):
            self.pending_folder_location = None
            reply = "Emergency stop acknowledged. Stopping all actions."
            self.memory.add_turn("user", clean_text)
            self.memory.add_turn("zeno", reply)
            return BrainResponse(kind="abort", message=reply)

        task_match = re.match(r"^(?:agent(?:\s+task)?|task)(?:\s*:\s*|\s+)(.+)$|^(?:do this task|complete this task)\s*[:,]?\s+(.+)$", clean_text, re.I | re.S)
        from .folder_intent import folder_name
        folder_text = next((part for part in task_match.groups() if part), clean_text) if task_match else clean_text
        folder = folder_request(folder_text)
        folder_agent = bool(agent_mode or task_match)
        if folder is None and self.pending_folder_location:
            name = folder_name(clean_text)
            explicit_name = re.match(r'^(?:call it|name it|name the folder|call the folder)\s+', clean_text, re.I)
            # Multi-word names can be supplied with "call it ...". A new command takes precedence.
            if re.fullmatch(r"yes|yeah|okay|ok|sure|go ahead", lowered):
                return BrainResponse(kind='chat', message='What name should I use? Say "call it" followed by the folder name.')
            bare_name = len(clean_text.split()) == 1 and not is_direct_command(clean_text)
            if name and (explicit_name or bare_name):
                location, pending_agent = self.pending_folder_location
                folder_agent = folder_agent or pending_agent
                folder = {'location': location, 'name': name}
            self.pending_folder_location = None
        if folder:
            self.awaiting_clarification = False
            self.memory.add_turn('user', clean_text)
            if not folder['name']:
                self.pending_folder_location = (folder['location'], folder_agent)
                question = f'What should I name the folder in {folder["location"]}? For a name with spaces, say "call it" followed by the name.'
                self.memory.add_turn('zeno', question)
                return BrainResponse(kind='chat', message=question)
            self.pending_folder_location = None
            command = {'understood': True, 'action': 'folder_create',
                       'parameters': {'path': folder['location'] + '/' + folder['name']}}
            return BrainResponse(kind='action', message='Creating the folder.',
                                 actions=self.planner.plan(command), data={**command, 'agent_mode': folder_agent})
        if agent_mode or task_match:
            goal = next((part for part in task_match.groups() if part), clean_text) if task_match else clean_text
            return BrainResponse(kind="task", message=goal, data={"goal": goal})

        # ----------------------------------------------------------------------
        # 1. Identity / Greeting queries
        # ----------------------------------------------------------------------
        task_prefix = re.match(r"^(?:task\s*:\s*|task\s+|do (?:a |the )?task\s*:?\s+)", clean_text, re.IGNORECASE)
        if task_prefix:
            goal = clean_text[task_prefix.end():].strip()
            if not goal:
                return BrainResponse(kind="chat", message="Describe your goal after task:.")
            self.memory.add_turn("user", clean_text)
            self.awaiting_clarification = False
            return BrainResponse(kind="task", message=goal, data={"goal": goal})

        if lowered in ("who are you", "what is your name", "who are you?", "what's your name"):
            reply = f"I am {self.assistant_name}, an AI assistant. We can talk things through, explore ideas, or work on supported computer tasks."
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
        # 4. OS Automation Action intent
        # ----------------------------------------------------------------------
        from .nlu import split_commands
        direct = all(is_direct_command(part) for part in split_commands(clean_text))
        if reasoning_available(self.client) and (self.awaiting_clarification or not direct):
            try:
                decision = await route_request(self, clean_text)
                self.memory.add_turn("user", clean_text)
                self.awaiting_clarification = decision["kind"] == "clarify"
                kind = "chat" if decision["kind"] == "clarify" else decision["kind"]
                if kind == "chat":
                    self.memory.add_turn("zeno", decision["message"])
                return BrainResponse(kind=kind, message=decision["message"])
            except Exception as exc:
                logger.warning("Contextual routing failed: %s", exc)
                return BrainResponse(kind="chat", message=reasoning_failure_message(),
                                     data={"service_error": last_api_failure() or "invalid_response"})

        # Offline mode must not mistake a question containing 'restart' for a power command.
        if not reasoning_available(self.client) and not direct:
            from .companion import offline_reply
            reply = offline_reply(clean_text)
            self.memory.add_turn("user", clean_text)
            self.memory.add_turn("zeno", reply)
            return BrainResponse(kind="chat", message=reply)
        nlu_result = await self.nlu.understand(clean_text)
        action_type = nlu_result.get("action", "unknown")

        if nlu_result.get("understood", False) and action_type not in ("unknown", "unhandled", "none"):
            # Legitimate OS Action
            actions = self.planner.plan(nlu_result)
            confirm_msg = nlu_result.get("confirmation_message") or f"Planning action: {nlu_result.get('description', '')}"
            self.memory.add_turn("user", clean_text)
            return BrainResponse(
                kind="action",
                message=confirm_msg,
                actions=actions,
                data=nlu_result
            )

        # ----------------------------------------------------------------------
        # 5. Conversational Reasoning / Q&A Fallback
        # ----------------------------------------------------------------------
        if action_type == "blocked":
            return BrainResponse(kind="chat", message=nlu_result["confirmation_message"])
        chat_reply = await self._generate_conversational_reply(clean_text)
        self.memory.add_turn("user", clean_text)
        self.memory.add_turn("zeno", chat_reply)
        return BrainResponse(kind="chat", message=chat_reply)

    async def respond_to_mail(self, request):
        from awareness.gmail import GmailMailbox
        if self.gmail_mailbox is None:
            self.gmail_mailbox = GmailMailbox()
        return await self.gmail_mailbox.respond(request, self.client)
