import os
import time
import pytest
from executor import desktop_organizer as organizer
from executor.file_ops import FileOps


def test_review_and_apply(tmp_path, monkeypatch):
    from brain.planner import describe_action
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    documents = tmp_path / "Documents"
    monkeypatch.setattr(organizer, "user_folder", lambda name: desktop if name == "desktop" else documents)
    files = FileOps([str(desktop), str(documents)])
    for name in ("Screenshot (1).png", "receipt-April.pdf", "Active.docx", "Browser.lnk"):
        (desktop / name).write_bytes(b"sample")
    old = time.time() - 35 * 86400
    os.utime(desktop / "receipt-April.pdf", (old, old))
    action, prompt = organizer.plan_desktop(files)
    assert action.requires_permission and "Invoices and receipts" in describe_action(action)
    assert "Active.docx" not in prompt and len(list(desktop.iterdir())) == 4
    assert organizer.apply_desktop(files, action.parameters["moves"]).success
    assert (documents / "Desktop files/Invoices and receipts/receipt-April.pdf").is_file()
    assert (desktop / "Screenshots/Screenshot (1).png").is_file()
    assert (desktop / "Browser.lnk").exists() and (desktop / "Active.docx").exists()


def test_changed_file_stays_put(tmp_path, monkeypatch):
    monkeypatch.setattr(organizer, "user_folder", lambda name: tmp_path)
    files = FileOps([str(tmp_path)])
    shot = tmp_path / "Screenshot 1.png"
    shot.write_bytes(b"original")
    action, _ = organizer.plan_desktop(files)
    shot.write_bytes(b"new")
    assert not organizer.apply_desktop(files, action.parameters["moves"]).success
    assert shot.read_bytes() == b"new"

@pytest.mark.asyncio
async def test_spoken_command_routes_to_review(tmp_path, monkeypatch):
    from brain.zeno_brain import ZenoBrain
    from config import config
    monkeypatch.setattr(config, "ALLOWED_DIRS", [str(tmp_path)])
    monkeypatch.setattr(config, "MEMORY_FILE", str(tmp_path / "memory.json"))
    monkeypatch.setattr(organizer, "user_folder", lambda name: tmp_path)
    (tmp_path / "Screenshot 3.png").touch()
    response = await ZenoBrain().think("Hey Zeno, organise my desktop")
    assert response.kind == "action" and response.actions[0].requires_permission
    assert response.actions[0].action_type == "organize_desktop"
    assert (tmp_path / "Screenshot 3.png").exists()
