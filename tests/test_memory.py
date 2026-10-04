"""
Test atomic memory writes (Step 3.4):
Verify that _save_long_term_memory writes to a temp file first,
then atomically replaces the target via os.replace.
"""

import json
import os
from pathlib import Path
from unittest.mock import patch, call
from brain.memory import ZenoMemory


def test_atomic_memory_write_uses_tmp_then_replace(tmp_path):
    """Memory save must write to .tmp file then os.replace to final path."""
    mem_file = tmp_path / "zeno_memory.json"
    mem = ZenoMemory(storage_path=str(mem_file))

    with patch("brain.memory.os.replace", wraps=os.replace) as mock_replace:
        mem.remember_fact("color", "blue")
        # os.replace should have been called once, from tmp to target
        mock_replace.assert_called_once()
        args = mock_replace.call_args[0]
        # First arg is the temp path (should end with .tmp)
        assert str(args[0]).endswith(".tmp")
        # Second arg is the final target path
        assert str(args[1]) == str(mem_file)

    # The final file must contain the fact
    data = json.loads(mem_file.read_text(encoding="utf-8"))
    assert data["facts"]["color"] == "blue"


def test_atomic_memory_write_no_corruption_on_crash(tmp_path):
    """If writing to .tmp fails, original file must remain intact."""
    mem_file = tmp_path / "zeno_memory.json"
    mem = ZenoMemory(storage_path=str(mem_file))
    mem.remember_fact("pet", "cat")

    original_data = json.loads(mem_file.read_text(encoding="utf-8"))
    assert original_data["facts"]["pet"] == "cat"

    # Simulate a write error during temp file creation
    with patch("builtins.open", side_effect=IOError("disk full")):
        mem.remember_fact("pet", "dog")

    # Original file must be unchanged
    data_after = json.loads(mem_file.read_text(encoding="utf-8"))
    assert data_after["facts"]["pet"] == "cat"
