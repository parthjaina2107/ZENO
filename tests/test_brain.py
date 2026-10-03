"""
Unit and integration tests for ZENO Cognitive Brain:
- Short-Term Memory
- Long-Term Persistent Memory
- Multimodal Screen Vision Detection
- ZenoBrain Routing & Persona
"""

import os
import pytest
from pathlib import Path
from brain.memory import ZenoMemory
from brain.vision import ScreenVision
from brain.zeno_brain import ZenoBrain, BrainResponse
from config import config


@pytest.fixture
def temp_memory_file(tmp_path):
    mem_file = tmp_path / "test_zeno_memory.json"
    return str(mem_file)


def test_short_term_memory():
    mem = ZenoMemory(storage_path="scratch/dummy_mem.json")
    mem.clear_short_term()

    mem.add_turn("user", "Hello ZENO")
    mem.add_turn("zeno", "Hello! How can I assist you today?")

    history = mem.get_recent_history()
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["text"] == "Hello ZENO"
    assert history[1]["role"] == "zeno"

    formatted = mem.format_dialogue_context()
    assert "User: Hello ZENO" in formatted
    assert "ZENO: Hello!" in formatted


def test_long_term_persistent_memory(temp_memory_file):
    mem = ZenoMemory(storage_path=temp_memory_file)

    # Store fact
    res = mem.remember_fact("favorite_editor", "VS Code")
    assert "committed that to memory" in res.lower()

    # Recall fact
    val = mem.recall_fact("favorite_editor")
    assert val == "VS Code"

    # Verify persistent file was written
    assert Path(temp_memory_file).exists()

    # Reload from disk into new instance
    reloaded_mem = ZenoMemory(storage_path=temp_memory_file)
    assert reloaded_mem.recall_fact("favorite_editor") == "VS Code"

    # Forget fact
    forgot = reloaded_mem.forget_fact("favorite_editor")
    assert forgot is True
    assert reloaded_mem.recall_fact("favorite_editor") is None


def test_memory_intent_parsing(temp_memory_file):
    mem = ZenoMemory(storage_path=temp_memory_file)

    # Remember intent
    intent = mem.parse_memory_intent("Remember that my project path is C:\\voiceAgent")
    assert intent is not None
    assert intent["action"] == "memory_store"
    assert intent["key"] == "project_path" or "project" in intent["key"]
    assert "C:\\voiceAgent" in intent["value"]

    # Recall intent
    recall_intent = mem.parse_memory_intent("What is my project path?")
    assert recall_intent is not None
    assert recall_intent["action"] == "memory_recall"
    assert "C:\\voiceAgent" in recall_intent["message"]

    # Forget intent
    forget_intent = mem.parse_memory_intent("Forget my project path")
    assert forget_intent is not None
    assert forget_intent["action"] == "memory_forget"


def test_vision_intent_detection():
    vision = ScreenVision(api_key=None)

    assert vision.is_vision_query("Look at my screen and tell me what is wrong") is True
    assert vision.is_vision_query("What's on my screen right now?") is True
    assert vision.is_vision_query("Explain what is on the screen") is True
    assert vision.is_vision_query("Summarize my screen") is True

    # Non-vision commands
    assert vision.is_vision_query("Open Google Chrome") is False
    assert vision.is_vision_query("Check my battery percentage") is False
    assert vision.is_vision_query("Turn up volume") is False


@pytest.mark.asyncio
async def test_zeno_brain_routing(temp_memory_file):
    brain = ZenoBrain(api_key=None)
    brain.memory = ZenoMemory(storage_path=temp_memory_file)

    # 1. Persona query
    resp = await brain.think("Who are you?")
    assert resp.kind == "chat"
    assert "ZENO" in resp.message

    # 2. Wake prefix stripping
    cleaned = brain.strip_wake_prefix("Hey Zeno, open Chrome")
    assert cleaned.lower() == "open chrome"

    # 3. Memory storage command
    mem_resp = await brain.think("Hey ZENO, remember that my laptop model is ThinkPad")
    assert mem_resp.kind == "memory"
    assert "laptop_model" in brain.memory.get_all_facts() or "model" in str(brain.memory.get_all_facts())

    # 4. OS Action routing
    act_resp = await brain.think("Check battery level")
    assert act_resp.kind == "action"
    assert len(act_resp.actions) >= 1
    assert act_resp.actions[0].action_type == "system_info"


@pytest.mark.asyncio
async def test_zeno_brain_kill_switch():
    brain = ZenoBrain(api_key="")
    for cmd in ["stop", "cancel everything", "abort", "HALT"]:
        resp = await brain.think(cmd)
        assert resp.kind == "abort"
        assert "stop" in resp.message.lower() or "stopping" in resp.message.lower()

