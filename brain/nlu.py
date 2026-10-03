"""
Natural Language Understanding (NLU) Engine
Translates human voice/text commands into structured action plans using Google Gemini API,
with a robust local fallback rule parser when offline or when API key is not configured.
"""

import json
import logging
import re
import os
from typing import Dict, Any, Optional
from config import config
from .api_utils import call_gemini_with_fallback

logger = logging.getLogger("VoiceAgent.NLU")

# Known popular websites for instant browser resolution
KNOWN_WEBSITES = {
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "reddit": "https://www.reddit.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "whatsapp": "https://web.whatsapp.com",
    "linkedin": "https://www.linkedin.com",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "amazon": "https://www.amazon.com",
    "chatgpt": "https://chatgpt.com",
    "maps": "https://maps.google.com",
    "drive": "https://drive.google.com",
    "docs": "https://docs.google.com",
}

SYSTEM_PROMPT = """You are a computer control assistant. The user will give you voice commands.
Your job is to understand the intent and return a structured JSON response.

RESPOND ONLY WITH VALID JSON. No markdown backticks, no explanations.

JSON Format:
{
  "understood": true,
  "action": "action_type",
  "parameters": { ... },
  "description": "Human-readable description of what will happen",
  "risk_level": "low" | "medium" | "high",
  "confirmation_message": "What to ask the user before executing"
}

Available actions:
- open_app: { "app_name": "chrome" }
- close_app: { "process_name": "chrome.exe" }
- open_url: { "url": "https://..." }
- web_search: { "query": "search terms" }
- type_text: { "text": "hello world" }
- keyboard_shortcut: { "keys": ["ctrl", "s"] }
- run_command: { "command": "dir C:\\Users" }
- file_create: { "path": "...", "content": "..." }
- file_delete: { "path": "..." }
- file_move: { "source": "...", "destination": "..." }
- file_copy: { "source": "...", "destination": "..." }
- file_search: { "directory": "...", "pattern": "*.txt" }
- file_read: { "path": "..." }
- screenshot: {}
- volume_set: { "level": 50 }
- system_info: { "type": "battery" | "cpu" | "ram" | "disk" | "ip" | "time" }
- shutdown: { "mode": "shutdown" | "restart" | "sleep" | "lock" }
- mouse_click: { "x": 100, "y": 200, "button": "left" }
- multi_step: { "steps": [ ...array of above actions... ] }

Risk levels:
- low: Info queries, screenshots, volume, opening apps/urls
- medium: File operations, typing, running safe commands
- high: Deleting files, shutdown/restart/sleep/lock, terminal commands

If you don't understand the command, set "understood": false and suggest what the user might mean in "confirmation_message".
"""


class NLUEngine:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        self.client = None
        self._init_client()

    def _init_client(self):
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Gemini NLU client initialized successfully.")
            except Exception as e:
                logger.warning(f"Could not initialize Gemini Client: {e}")
                self.client = None
        else:
            logger.info("No Gemini API key provided. Using built-in local fallback NLU.")

    def update_api_key(self, api_key: str):
        self.api_key = api_key
        self._init_client()

    def _clean_json_string(self, text: str) -> str:
        """Strip markdown codeblocks or leading/trailing non-json noise."""
        text = text.strip()
        # Remove ```json and ```
        text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        
        # If there are braces, extract first outer JSON object
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()

    def _sanitize_command(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Validate safety constraints on parsed commands."""
        action = response.get("action")
        params = response.get("parameters", {})

        if action == "run_command":
            cmd = str(params.get("command", "")).lower()
            for blocked in config.BLOCKED_COMMANDS:
                if blocked in cmd:
                    logger.warning(f"Blocked dangerous command requested: {cmd}")
                    return {
                        "understood": False,
                        "action": "blocked",
                        "parameters": {},
                        "description": f"Security violation: command '{blocked}' is blocked for system safety.",
                        "risk_level": "high",
                        "confirmation_message": f"I cannot execute that command because '{blocked}' is blocked for safety."
                    }

        if action in ("file_create", "file_delete", "file_read"):
            path = str(params.get("path", ""))
            for blocked in config.BLOCKED_PATHS:
                if blocked.lower() in path.lower():
                    logger.warning(f"Blocked dangerous file path requested: {path}")
                    return {
                        "understood": False,
                        "action": "blocked",
                        "parameters": {},
                        "description": f"Security violation: path in {blocked} is blocked.",
                        "risk_level": "high",
                        "confirmation_message": f"I cannot access files in {blocked} for safety reasons."
                    }

        return response

    def _local_fallback_understand(self, text: str) -> Dict[str, Any]:
        """Built-in regex/keyword parser for reliable offline operation."""
        lowered = text.lower().strip()

        # System Info queries
        if any(w in lowered for w in ["battery", "charge", "power percentage", "battery percentage", "battery level"]):
            return {
                "understood": True,
                "action": "system_info",
                "parameters": {"type": "battery"},
                "description": "Check device battery level and charging status",
                "risk_level": "low",
                "confirmation_message": "Checking battery level."
            }
        if any(w in lowered for w in ["cpu", "processor usage", "processor load", "cpu usage"]):
            return {
                "understood": True,
                "action": "system_info",
                "parameters": {"type": "cpu"},
                "description": "Check current CPU utilization percentage",
                "risk_level": "low",
                "confirmation_message": "Checking CPU usage."
            }
        if any(w in lowered for w in ["ram", "memory usage", "memory", "ram usage"]):
            return {
                "understood": True,
                "action": "system_info",
                "parameters": {"type": "ram"},
                "description": "Check RAM memory usage",
                "risk_level": "low",
                "confirmation_message": "Checking RAM usage."
            }
        if any(w in lowered for w in ["disk", "storage", "drive space", "hard drive", "free space"]):
            return {
                "understood": True,
                "action": "system_info",
                "parameters": {"type": "disk"},
                "description": "Check hard drive storage space",
                "risk_level": "low",
                "confirmation_message": "Checking disk storage."
            }
        if any(w in lowered for w in ["ip", "ip address", "network address", "my ip"]):
            return {
                "understood": True,
                "action": "system_info",
                "parameters": {"type": "ip"},
                "description": "Check local IP address",
                "risk_level": "low",
                "confirmation_message": "Checking IP address."
            }
        if any(w in lowered for w in ["time", "clock", "date"]):
            return {
                "understood": True,
                "action": "system_info",
                "parameters": {"type": "time"},
                "description": "Get current system time",
                "risk_level": "low",
                "confirmation_message": "Checking current time."
            }

        # Screenshot
        if "screenshot" in lowered or "capture screen" in lowered or "snap screen" in lowered:
            return {
                "understood": True,
                "action": "screenshot",
                "parameters": {},
                "description": "Capture current desktop screenshot",
                "risk_level": "low",
                "confirmation_message": "Take a screenshot now?"
            }

        # Volume
        volume_match = re.search(r"volume\s+(?:to\s+)?(\d+)", lowered)
        if volume_match:
            level = int(volume_match.group(1))
            return {
                "understood": True,
                "action": "volume_set",
                "parameters": {"level": level},
                "description": f"Set system volume to {level}%",
                "risk_level": "low",
                "confirmation_message": f"Set volume to {level}%?"
            }
        if "mute" in lowered:
            return {
                "understood": True,
                "action": "volume_set",
                "parameters": {"level": 0},
                "description": "Mute system volume",
                "risk_level": "low",
                "confirmation_message": "Mute system volume?"
            }

        # Web Search
        search_match = re.search(r"(?:search|google|look up)\s+(?:for\s+)?(.+)", lowered)
        if search_match:
            query = search_match.group(1).strip()
            return {
                "understood": True,
                "action": "web_search",
                "parameters": {"query": query},
                "description": f"Search Google for '{query}'",
                "risk_level": "low",
                "confirmation_message": f"Search Google for '{query}'?"
            }

        # Open URL
        url_match = re.search(r"(?:open|go to|visit)\s+(https?://\S+|www\.\S+|\S+\.(?:com|org|io|net|edu|dev))", lowered)
        if url_match:
            url = url_match.group(1).strip()
            return {
                "understood": True,
                "action": "open_url",
                "parameters": {"url": url},
                "description": f"Open URL {url} in browser",
                "risk_level": "low",
                "confirmation_message": f"Open {url}?"
            }

        # Open App or Known Website
        open_match = re.search(r"(?:open|launch|start|go to)\s+([a-zA-Z0-9_\- ]+)", lowered)
        if open_match:
            app_raw = open_match.group(1).strip()
            # Strip browser context words: "in chrome", "in browser", "in edge", etc.
            app_clean = re.sub(
                r"\s+(?:in|on|using|with)\s+(?:chrome|edge|firefox|browser|brave).*",
                "",
                app_raw,
                flags=re.IGNORECASE
            ).strip().lower()

            if app_clean in KNOWN_WEBSITES:
                return {
                    "understood": True,
                    "action": "open_url",
                    "parameters": {"url": KNOWN_WEBSITES[app_clean]},
                    "description": f"Open {app_clean.title()} in browser",
                    "risk_level": "low",
                    "confirmation_message": f"Open {app_clean.title()}?"
                }

            return {
                "understood": True,
                "action": "open_app",
                "parameters": {"app_name": app_raw},
                "description": f"Open application '{app_raw}'",
                "risk_level": "low",
                "confirmation_message": f"Open application '{app_raw}'?"
            }

        # Close App
        close_match = re.search(r"(?:close|kill|exit|stop)\s+([a-zA-Z0-9_\- ]+)", lowered)
        if close_match:
            app = close_match.group(1).strip()
            return {
                "understood": True,
                "action": "close_app",
                "parameters": {"process_name": app},
                "description": f"Close application '{app}'",
                "risk_level": "medium",
                "confirmation_message": f"Close application '{app}'?"
            }

        # Shutdown / Restart / Lock
        if "shutdown" in lowered:
            return {
                "understood": True,
                "action": "shutdown",
                "parameters": {"mode": "shutdown"},
                "description": "Shutdown the computer in 5 seconds",
                "risk_level": "high",
                "confirmation_message": "Are you sure you want to SHUT DOWN your computer?"
            }
        if "restart" in lowered or "reboot" in lowered:
            return {
                "understood": True,
                "action": "shutdown",
                "parameters": {"mode": "restart"},
                "description": "Restart the computer in 5 seconds",
                "risk_level": "high",
                "confirmation_message": "Are you sure you want to RESTART your computer?"
            }
        if "lock" in lowered or "lock screen" in lowered:
            return {
                "understood": True,
                "action": "shutdown",
                "parameters": {"mode": "lock"},
                "description": "Lock the Windows session",
                "risk_level": "medium",
                "confirmation_message": "Lock computer workstation?"
            }

        # Typing text
        type_match = re.search(r"(?:type|write)\s+(.+)", lowered)
        if type_match:
            typed = type_match.group(1).strip()
            return {
                "understood": True,
                "action": "type_text",
                "parameters": {"text": typed},
                "description": f"Type text: '{typed}'",
                "risk_level": "medium",
                "confirmation_message": f"Type '{typed}'?"
            }

        # Terminal / Shell commands
        cmd_match = re.search(r"(?:run command|execute command|run in terminal|terminal)\s+(.+)", lowered)
        if cmd_match:
            cmd = cmd_match.group(1).strip()
            return {
                "understood": True,
                "action": "run_command",
                "parameters": {"command": cmd},
                "description": f"Run command: '{cmd}'",
                "risk_level": "high",
                "confirmation_message": f"Run command '{cmd}' in terminal?"
            }

        # Quick bypass for conversational questions (lets ZenoBrain jump straight to conversational chat)
        if lowered.startswith(("what is ", "what are ", "who is ", "who was ", "why is ", "why do ", "how do ", "how does ", "how can ", "tell me ", "explain ", "can you explain ")) and not any(w in lowered for w in ["battery", "cpu", "ram", "disk", "time", "ip"]):
            return {
                "understood": False,
                "action": "none",
                "parameters": {"raw_text": text},
                "description": f"Conversational query: '{text}'",
                "risk_level": "low",
                "confirmation_message": ""
            }

        return {
            "understood": False,
            "action": "unknown",
            "parameters": {"raw_text": text},
            "description": f"Could not determine intent for: '{text}'",
            "risk_level": "low",
            "confirmation_message": f"I didn't quite catch that. Did you mean to search or open an app?"
        }

    async def understand(self, user_text: str) -> Dict[str, Any]:
        """
        Analyze user text and return parsed action dictionary.
        FAST PATH: Tries local parser first for instant (<1ms) response on common commands.
        SLOW PATH: Falls back to Gemini API with retry and model fallback for complex/unhandled queries.
        """
        if not user_text or not user_text.strip():
            return {
                "understood": False,
                "action": "none",
                "parameters": {},
                "description": "Empty input received.",
                "risk_level": "low",
                "confirmation_message": "I didn't hear anything. Please try speaking again."
            }

        text = user_text.strip()

        # FAST PATH: Try local parser first — handles ~80% of OS commands in <1ms
        local_result = self._local_fallback_understand(text)
        if local_result.get("understood", False):
            return self._sanitize_command(local_result)

        # If detected as purely conversational, skip LLM NLU round-trip (ZenoBrain will handle via chat)
        if local_result.get("action") == "none":
            return self._sanitize_command(local_result)

        # SLOW PATH: If Gemini client is active, attempt Gemini call with fallback chain & retries
        if self.client:
            prompt = f"{SYSTEM_PROMPT}\n\nUser command: \"{text}\"\nJSON:"
            try:
                response = await call_gemini_with_fallback(
                    client=self.client,
                    contents=prompt,
                    primary_model=getattr(config, "GEMINI_MODEL", "gemini-3.8-flash")
                )
                if response and hasattr(response, "text") and response.text:
                    raw_json = response.text
                    cleaned = self._clean_json_string(raw_json)
                    parsed = json.loads(cleaned)

                    # Check required fields
                    if "understood" in parsed and "action" in parsed:
                        return self._sanitize_command(parsed)
            except Exception as e:
                logger.warning(f"Gemini API request failed ({e}); using local NLU fallback.")

        # Return sanitized local fallback
        return self._sanitize_command(local_result)
