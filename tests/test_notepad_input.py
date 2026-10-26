from unittest.mock import MagicMock
import pytest
from executor.notepad_input import NotepadInput
from brain.nlu import NLUEngine


def test_notepad_paste_preserves_document_and_verifies_before_clipboard_restore():
    helper = NotepadInput()
    window, editor = MagicMock(), MagicMock()
    helper.find_editor = MagicMock(return_value=(window, editor))
    helper.read = MagicMock(side_effect=["Existing\n", "Existing\nHello ZENO"])
    clipboard, keyboard = MagicMock(), MagicMock()
    clipboard.paste.return_value = "Original clipboard"
    output = helper.paste("Hello ZENO", clipboard, keyboard)
    assert output["verified"] is True
    editor.set_focus.assert_called_once()
    assert clipboard.copy.call_args_list[-1].args[0] == "Original clipboard"
    assert keyboard.hotkey.call_args_list[0].args == ("ctrl", "end")


def test_unverified_paste_restores_clipboard_and_reports_failure(monkeypatch):
    helper = NotepadInput()
    helper.find_editor = MagicMock(return_value=(MagicMock(), MagicMock()))
    helper.read = MagicMock(return_value="Unchanged")
    clipboard = MagicMock()
    clipboard.paste.return_value = "Original clipboard"
    monkeypatch.setattr("executor.notepad_input.time.monotonic", MagicMock(side_effect=[0, 5]))
    with pytest.raises(RuntimeError, match="did not contain"):
        helper.paste("Hello", clipboard, MagicMock())
    assert clipboard.copy.call_args_list[-1].args[0] == "Original clipboard"


def test_compound_notepad_command_and_standalone_typing_preserve_case():
    nlu = NLUEngine(api_key="")
    parsed = nlu._local_fallback_understand("Open Notepad and type Hello ZENO")
    assert parsed["action"] == "multi_step"
    assert parsed["parameters"]["steps"][1]["parameters"]["text"] == "Hello ZENO"
    assert nlu._local_fallback_understand("type Hello ZENO")["parameters"]["text"] == "Hello ZENO"
