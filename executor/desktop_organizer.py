"""Build a reviewable desktop filing plan from local file metadata."""
import os
import re
import stat
import time
from pathlib import Path

import app_access
from brain.planner import ActionResult, PlannedAction
from user_paths import user_folder

REQUEST = re.compile(r"(?:please )?(?:(?:can|could|would) you )?(?:organize|organise|arrange|tidy(?: up)?|clean up|sort) (?:my |the )?desktop(?: files)?(?: please)?[.!?]*", re.I)
GROUPS = {
    "Pictures": {".png", ".jpg", ".jpeg", ".webp", ".gif"},
    "Documents": {".pdf", ".docx", ".txt", ".xlsx", ".pptx", ".odt", ".csv"},
    "Archives": {".zip", ".7z", ".rar"},
}


def candidate(path, desktop, files, now):
    valid, source, _ = files._resolve_and_validate_path(str(path))
    if not valid or source != path:
        return None
    try:
        info = path.lstat()
    except OSError:
        return None
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or path.name.startswith((".", "~"))
            or getattr(info, "st_file_attributes", 0) & (stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM | stat.FILE_ATTRIBUTE_REPARSE_POINT)):
        return None
    group = next((name for name, extensions in GROUPS.items() if path.suffix.lower() in extensions), None)
    if not group:
        return None
    if group == "Pictures" and re.match(r"^(?:screen[ _-]?shot|screen capture)\b", path.stem.replace("_", " "), re.I):
        dest = desktop / "Screenshots" / path.name
        reason = "Screenshot grouped with other captures"
    elif now - info.st_mtime >= 30 * 86400:
        words = set(re.findall(r"[a-z]+", path.stem.lower()))
        if group == "Documents" and words.intersection({"invoice", "invoices", "receipt", "receipts"}):
            group = "Invoices and receipts"
        dest = user_folder("documents").resolve() / "Desktop files" / group / path.name
        reason = f"{group}, last edited at least 30 days ago"
    else:
        return None
    okay, resolved, _ = files._resolve_and_validate_path(str(dest))
    if not okay or resolved != dest or dest.exists() or dest.is_symlink():
        return None
    return {"source": str(path), "destination": str(dest), "reason": reason,
            "stamp": [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns]}


def plan_desktop(files):
    if not app_access.allowed("files"):
        return None, app_access.denial("files")
    desktop = user_folder("desktop").resolve()
    allowed, _, error = files._resolve_and_validate_path(str(desktop))
    if not allowed:
        return None, error
    moves = []
    try:
        now = time.time()
        for path in sorted(desktop.iterdir(), key=lambda p: p.name.casefold()):
            move = candidate(path, desktop, files, now)
            if move:
                moves.append(move)
                if len(moves) == 10:
                    break
    except (OSError, ValueError):
        return None, "I couldn't finish checking your Desktop. No files were moved."
    if not moves:
        return None, "I found no loose screenshots or older documents, pictures or archives with a free destination. I left your Desktop as it is."
    review = "Review these Desktop moves (up to 10 at a time):\n" + "\n".join(
        f"{Path(m['source']).name} → {m['destination']} — {m['reason']}" for m in moves)
    return PlannedAction("organize_desktop", {"moves": moves}, description=review, confirmation_message=review), review


def apply_desktop(files, moves):
    desktop = user_folder("desktop").resolve()
    moved = 0
    for move in moves:
        path = Path(move["source"])
        if not app_access.allowed("files") or path.parent != desktop or candidate(path, desktop, files, time.time()) != move:
            return ActionResult(False, f"Moved {moved} of {len(moves)} files. Access, a file, or its destination changed. Ask me to review the Desktop again.")
        dest = Path(move["destination"])
        if not files.folder_create(str(dest.parent)).success:
            return ActionResult(False, f"Moved {moved} files. Could not prepare {dest.parent}.")
        # Windows rename refuses collisions and cross-volume moves. Leave the source intact in either case.
        try:
            if os.name != "nt":
                raise OSError("Windows desktop required")
            os.rename(path, dest)
        except OSError:
            return ActionResult(False, f"Moved {moved} files. Could not move {path.name} to {dest.parent}.")
        moved += 1
    return ActionResult(True, f"Moved {moved} Desktop files to the reviewed folders. All other items stayed in place.")
