"""
File Operations for Voice Agent:
Safe file creation, deletion via Recycle Bin (send2trash), copy/move, search, and reading
with path validation against allowed user directories and system protection.
"""

import os
import glob
import shutil
from pathlib import Path
import logging
from typing import Optional, List, Dict, Any
from brain.planner import ActionResult
from config import config

logger = logging.getLogger("VoiceAgent.FileOps")


class FileOps:
    def __init__(self, allowed_dirs: Optional[List[str]] = None):
        self.allowed_dirs = [Path(d).resolve() for d in (allowed_dirs or config.ALLOWED_DIRS)]

    def _resolve_and_validate_path(self, path_str: str) -> tuple[bool, Optional[Path], Optional[str]]:
        """
        Validate path:
        1. Resolve relative and absolute paths
        2. Block path traversal attempts (..) escaping allowed directories
        3. Reject system-critical directories
        """
        if not path_str or not path_str.strip():
            return False, None, "Path cannot be empty."

        clean = path_str.strip()
        # Handle desktop/documents/downloads shortcuts
        home = Path.home()
        if clean.lower().startswith("desktop/") or clean.lower().startswith("desktop\\") or clean.lower() == "desktop":
            clean = str(home / "Desktop" / clean[7:].lstrip("\\/"))
        elif clean.lower().startswith("documents/") or clean.lower().startswith("documents\\") or clean.lower() == "documents":
            clean = str(home / "Documents" / clean[9:].lstrip("\\/"))
        elif clean.lower().startswith("downloads/") or clean.lower().startswith("downloads\\") or clean.lower() == "downloads":
            clean = str(home / "Downloads" / clean[9:].lstrip("\\/"))

        target = Path(clean).expanduser().resolve()
        target_str = str(target).lower()

        # Check blocked paths
        for blocked in config.BLOCKED_PATHS:
            if blocked.lower() in target_str:
                return False, None, f"Access denied: Path is inside restricted system directory '{blocked}'."

        # Check if inside allowed directory
        is_allowed = False
        for allowed in self.allowed_dirs:
            try:
                target.relative_to(allowed)
                is_allowed = True
                break
            except ValueError:
                continue

        if not is_allowed:
            allowed_names = [d.name or str(d) for d in self.allowed_dirs]
            return False, None, f"Access denied: Path '{target}' is outside permitted directories ({', '.join(allowed_names)})."

        return True, target, None

    def file_create(self, path: str, content: str = "") -> ActionResult:
        """Create a new file or write content to a file safely."""
        valid, target, err = self._resolve_and_validate_path(path)
        if not valid or not target:
            return ActionResult(success=False, message=err or "Invalid path.", error="PATH_VALIDATION_FAILED")

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            return ActionResult(
                success=True,
                message=f"Created file at: {target} ({len(content)} characters written).",
                output={"path": str(target), "bytes": len(content)}
            )
        except Exception as e:
            return ActionResult(success=False, message=f"Failed to create file: {e}", error=str(e))

    def file_delete(self, path: str, permanent: bool = False) -> ActionResult:
        """Delete a file safely by moving it to the Recycle Bin (send2trash)."""
        valid, target, err = self._resolve_and_validate_path(path)
        if not valid or not target:
            return ActionResult(success=False, message=err or "Invalid path.", error="PATH_VALIDATION_FAILED")

        if not target.exists():
            return ActionResult(success=False, message=f"File does not exist: {target}", error="FILE_NOT_FOUND")

        try:
            if permanent:
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
                return ActionResult(success=True, message=f"Permanently removed: {target}")
            else:
                import send2trash
                send2trash.send2trash(str(target))
                return ActionResult(success=True, message=f"Moved to Recycle Bin: {target}")
        except Exception as e:
            return ActionResult(success=False, message=f"Failed to delete file: {e}", error=str(e))

    def file_move(self, source: str, destination: str) -> ActionResult:
        """Move a file or directory after validating source and destination."""
        s_valid, s_target, s_err = self._resolve_and_validate_path(source)
        if not s_valid or not s_target:
            return ActionResult(success=False, message=f"Source error: {s_err}", error="SOURCE_PATH_ERROR")

        d_valid, d_target, d_err = self._resolve_and_validate_path(destination)
        if not d_valid or not d_target:
            return ActionResult(success=False, message=f"Destination error: {d_err}", error="DEST_PATH_ERROR")

        if not s_target.exists():
            return ActionResult(success=False, message=f"Source file not found: {s_target}", error="SOURCE_NOT_FOUND")

        try:
            d_target.parent.mkdir(parents=True, exist_ok=True)
            res = shutil.move(str(s_target), str(d_target))
            return ActionResult(success=True, message=f"Moved '{s_target.name}' to: {res}")
        except Exception as e:
            return ActionResult(success=False, message=f"Failed to move file: {e}", error=str(e))

    def file_copy(self, source: str, destination: str) -> ActionResult:
        """Copy a file after validating paths."""
        s_valid, s_target, s_err = self._resolve_and_validate_path(source)
        if not s_valid or not s_target:
            return ActionResult(success=False, message=f"Source error: {s_err}", error="SOURCE_PATH_ERROR")

        d_valid, d_target, d_err = self._resolve_and_validate_path(destination)
        if not d_valid or not d_target:
            return ActionResult(success=False, message=f"Destination error: {d_err}", error="DEST_PATH_ERROR")

        if not s_target.exists():
            return ActionResult(success=False, message=f"Source not found: {s_target}", error="SOURCE_NOT_FOUND")

        try:
            d_target.parent.mkdir(parents=True, exist_ok=True)
            if s_target.is_dir():
                res = shutil.copytree(str(s_target), str(d_target), dirs_exist_ok=True)
            else:
                res = shutil.copy2(str(s_target), str(d_target))
            return ActionResult(success=True, message=f"Copied '{s_target.name}' to: {res}")
        except Exception as e:
            return ActionResult(success=False, message=f"Failed to copy file: {e}", error=str(e))

    def file_read(self, path: str, max_lines: int = 200) -> ActionResult:
        """Read content of a text file (up to max_lines)."""
        valid, target, err = self._resolve_and_validate_path(path)
        if not valid or not target:
            return ActionResult(success=False, message=err or "Invalid path.", error="PATH_VALIDATION_FAILED")

        if not target.exists():
            return ActionResult(success=False, message=f"File not found: {target}", error="FILE_NOT_FOUND")

        if not target.is_file():
            return ActionResult(success=False, message=f"Path is not a file: {target}", error="NOT_A_FILE")

        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                lines = [f.readline() for _ in range(max_lines)]
                content = "".join(lines)
            return ActionResult(
                success=True,
                message=f"Read {len(lines)} lines from {target.name}.",
                output=content
            )
        except Exception as e:
            return ActionResult(success=False, message=f"Failed to read file: {e}", error=str(e))

    def file_search(self, directory: str, pattern: str = "*") -> ActionResult:
        """Search files matching wildcard pattern in directory (max 50 results)."""
        valid, target_dir, err = self._resolve_and_validate_path(directory)
        if not valid or not target_dir:
            return ActionResult(success=False, message=err or "Invalid path.", error="PATH_VALIDATION_FAILED")

        if not target_dir.exists() or not target_dir.is_dir():
            return ActionResult(success=False, message=f"Directory not found: {target_dir}", error="DIR_NOT_FOUND")

        try:
            matches = []
            for p in target_dir.glob(pattern):
                if p.is_file():
                    matches.append({"name": p.name, "path": str(p), "size_bytes": p.stat().st_size})
                if len(matches) >= 50:
                    break

            return ActionResult(
                success=True,
                message=f"Found {len(matches)} file(s) matching '{pattern}' in {target_dir.name}.",
                output=matches
            )
        except Exception as e:
            return ActionResult(success=False, message=f"Search failed: {e}", error=str(e))
