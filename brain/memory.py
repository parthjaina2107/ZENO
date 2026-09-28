"""
ZENO Memory Architecture
Provides dual-layer memory:
1. Short-Term Memory: Ephemeral multi-turn conversational context.
2. Long-Term Memory: Persistent disk-backed store for user preferences, facts, and custom aliases.
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from config import config

logger = logging.getLogger("VoiceAgent.Memory")


class ZenoMemory:
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path or config.MEMORY_FILE)
        self.short_term_history: List[Dict[str, Any]] = []
        self.max_history_turns = 12
        self.long_term_data: Dict[str, Any] = {
            "facts": {},
            "user_preferences": {},
            "custom_aliases": {}
        }
        self._load_long_term_memory()

    def _load_long_term_memory(self):
        """Load persistent memory from JSON file if available."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.long_term_data.update(data)
                logger.info(f"Loaded {len(self.long_term_data.get('facts', {}))} facts from {self.storage_path}")
            except Exception as e:
                logger.warning(f"Could not load persistent memory from {self.storage_path}: {e}")
        else:
            self._save_long_term_memory()

    def _save_long_term_memory(self):
        """Persist long-term memory to disk."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.long_term_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save persistent memory to {self.storage_path}: {e}")

    # === SHORT-TERM CONVERSATIONAL MEMORY ===

    def add_turn(self, role: str, text: str):
        """Record a single conversational turn ('user' or 'zeno')."""
        clean_text = text.strip()
        if not clean_text:
            return
        self.short_term_history.append({
            "role": role.lower(),
            "text": clean_text,
            "timestamp": time.time()
        })
        # Slide window if history exceeds max
        if len(self.short_term_history) > self.max_history_turns:
            self.short_term_history = self.short_term_history[-self.max_history_turns:]

    def get_recent_history(self, limit: int = 6) -> List[Dict[str, str]]:
        """Return the most recent dialogue turns formatted for LLM prompts."""
        recent = self.short_term_history[-limit:]
        return [{"role": item["role"], "text": item["text"]} for item in recent]

    def format_dialogue_context(self, limit: int = 6) -> str:
        """Format dialogue history into a prompt string."""
        turns = self.get_recent_history(limit)
        if not turns:
            return ""
        lines = []
        for t in turns:
            speaker = "User" if t["role"] == "user" else "ZENO"
            lines.append(f"{speaker}: {t['text']}")
        return "\n".join(lines)

    def clear_short_term(self):
        """Clear conversation history."""
        self.short_term_history.clear()

    # === LONG-TERM PERSISTENT MEMORY ===

    def remember_fact(self, key: str, value: str, category: str = "facts") -> str:
        """Save a key-value fact into long-term memory."""
        k = key.lower().strip().replace(" ", "_")
        v = value.strip()
        if category not in self.long_term_data:
            self.long_term_data[category] = {}
        self.long_term_data[category][k] = v
        self._save_long_term_memory()
        logger.info(f"Remembered in {category}: '{k}' = '{v}'")
        return f"I've committed that to memory: {key} is {value}."

    def recall_fact(self, key: str, category: str = "facts") -> Optional[str]:
        """Retrieve a specific fact by key."""
        k = key.lower().strip().replace(" ", "_")
        category_data = self.long_term_data.get(category, {})
        # Exact match
        if k in category_data:
            return category_data[k]
        # Partial match
        for existing_key, val in category_data.items():
            if k in existing_key or existing_key in k:
                return val
        return None

    def forget_fact(self, key: str, category: str = "facts") -> bool:
        """Remove a fact from long-term memory."""
        k = key.lower().strip().replace(" ", "_")
        category_data = self.long_term_data.get(category, {})
        if k in category_data:
            del category_data[k]
            self._save_long_term_memory()
            return True
        # Try partial match
        matched_key = None
        for existing_key in category_data:
            if k in existing_key:
                matched_key = existing_key
                break
        if matched_key:
            del category_data[matched_key]
            self._save_long_term_memory()
            return True
        return False

    def get_all_facts(self) -> Dict[str, Any]:
        """Return all stored memories."""
        return self.long_term_data.get("facts", {})

    def format_memory_for_prompt(self) -> str:
        """Format persistent facts for injecting into LLM system prompt."""
        facts = self.get_all_facts()
        if not facts:
            return ""
        lines = [f"- {k.replace('_', ' ').capitalize()}: {v}" for k, v in facts.items()]
        return "User Personal Knowledge & Memories:\n" + "\n".join(lines)

    # === NATURAL LANGUAGE MEMORY PARSER ===

    def parse_memory_intent(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Check if the user input is a direct memory instruction.
        Examples:
        - 'Remember that my favorite programming language is Python'
        - 'Remember my project path is C:\\Dev'
        - 'What is my favorite programming language?'
        - 'Forget my project path'
        - 'What do you remember about me?'
        """
        lowered = text.strip().lower()

        # 1. Listing all memories
        if any(p in lowered for p in [
            "what do you remember", "list my memories", "show my memories",
            "what memories do you have", "what do you know about me"
        ]):
            facts = self.get_all_facts()
            if not facts:
                msg = "My memory is currently clear. You can ask me to remember anything by saying 'Remember that [thing] is [value]'."
            else:
                formatted = ", ".join([f"{k.replace('_', ' ')}: {v}" for k, v in facts.items()])
                msg = f"Here is what I remember about you: {formatted}."
            return {"action": "memory_list", "message": msg}

        # 2. Remembering a fact: "Remember that X is Y" or "Remember X is Y"
        remember_match = re.search(r"(?:please\s+)?remember\s+(?:that\s+)?(.+?)\s+(?:is|=|as)\s+(.+)", text, re.IGNORECASE)
        if remember_match:
            key = remember_match.group(1).strip()
            # Clean common filler prefixes
            key = re.sub(r"^(my|the)\s+", "", key, flags=re.IGNORECASE)
            val = remember_match.group(2).strip()
            msg = self.remember_fact(key, val)
            return {"action": "memory_store", "key": key, "value": val, "message": msg}

        # 3. Forgetting a fact: "Forget my X" or "Delete memory of X"
        forget_match = re.search(r"(?:please\s+)?(?:forget|delete\s+memory\s+of)\s+(?:that\s+)?(?:my\s+|the\s+)?(.+)", text, re.IGNORECASE)
        if forget_match:
            key = forget_match.group(1).strip().rstrip("?.!")
            success = self.forget_fact(key)
            if success:
                msg = f"I've removed {key} from my memory."
            else:
                msg = f"I don't have any recorded memory for '{key}'."
            return {"action": "memory_forget", "key": key, "message": msg}

        # 4. Recalling a specific fact: "What is my X?" or "What did I tell you about my X?"
        recall_match = re.search(r"(?:what\s+is\s+my|what's\s+my|do\s+you\s+remember\s+my|what\s+did\s+i\s+say\s+about\s+my)\s+(.+)", text, re.IGNORECASE)
        if recall_match:
            key = recall_match.group(1).strip().rstrip("?.!")
            val = self.recall_fact(key)
            if val:
                msg = f"According to my memory, your {key} is {val}."
                return {"action": "memory_recall", "key": key, "value": val, "message": msg}

        return None
