"""
File Operations for Voice Agent:
Safe file creation, deletion via Recycle Bin (send2trash), copy/move, search, and reading
with path validation against allowed user directories and system protection.
"""

import errno
import os
import shutil
import tempfile
from itertools import islice
from pathlib import Path
import logging
from typing import Optional, List, Dict, Any
from brain.planner import ActionResult
from config import config
from user_paths import user_folder
from .file_publication import stage_new_file

logger = logging.getLogger("VoiceAgent.FileOps")


def _copy_to_new_path(source: Path, destination: Path):
    """Copy to an exact destination. Publish only into a free name."""
    if source.is_dir():
        if destination.is_relative_to(source):
            raise ValueError("A folder cannot be copied inside itself.")
        if destination.exists():
            raise FileExistsError(str(destination))
        if os.name == "nt":
            with tempfile.TemporaryDirectory(dir=destination.parent, prefix=".zeno-") as temporary:
                staged = Path(temporary) / "tree"
                shutil.copytree(source, staged, symlinks=True)
                os.rename(staged, destination)
        else:
            shutil.copytree(source, destination, symlinks=True)
    else:
        with stage_new_file(destination) as staged:
            shutil.copy2(source, staged)


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
        if clean.lower().startswith("desktop/") or clean.lower().startswith("desktop\\") or clean.lower() == "desktop":
            clean = str(user_folder('desktop') / clean[7:].lstrip("\\/"))
        elif clean.lower().startswith("documents/") or clean.lower().startswith("documents\\") or clean.lower() == "documents":
            clean = str(user_folder('documents') / clean[9:].lstrip("\\/"))
        elif clean.lower().startswith("downloads/") or clean.lower().startswith("downloads\\") or clean.lower() == "downloads":
            clean = str(user_folder('downloads') / clean[9:].lstrip("\\/"))

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

    def folder_create(self, path: str) -> ActionResult:
        valid, target, error = self._resolve_and_validate_path(path)
        if not valid or target is None:
            return ActionResult(success=False, message=error or 'Invalid folder path.', error='PATH_VALIDATION_FAILED')
        try:
            existed = target.is_dir()
            target.mkdir(parents=True, exist_ok=True)
            return ActionResult(success=True,
                                message=f'Folder "{target.name}" already exists.' if existed else f'Created folder "{target.name}".',
                                output={'path': str(target), 'verified': target.is_dir(), 'created': not existed})
        except FileExistsError:
            return ActionResult(success=False, message='A file already uses that name. Choose a different folder name.', error='PATH_EXISTS')
        except OSError:
            return ActionResult(success=False, message='Windows could not create this folder. Check the location and your access.', error='FOLDER_CREATE_FAILED')

    def file_create(self, path: str, content: str = "") -> ActionResult:
        """Create a new file or write content to a file safely."""
        valid, target, err = self._resolve_and_validate_path(path)
        if not valid or not target:
            return ActionResult(success=False, message=err or "Invalid path.", error="PATH_VALIDATION_FAILED")

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with stage_new_file(target) as staged:
                written = staged.write_bytes(content.encode("utf-8"))
            return ActionResult(
                success=True,
                message=f"Created file at: {target} ({len(content)} characters written).",
                output={"path": str(target), "bytes": written}
            )
        except FileExistsError:
            return ActionResult(False, "A file already exists at that path. Choose a new name.", error="PATH_EXISTS")
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
            if d_target.exists() and (not d_target.is_dir() or (d_target / s_target.name).exists()):
                return ActionResult(False, "Destination already exists.", error="PATH_EXISTS")
            res = d_target / s_target.name if d_target.is_dir() else d_target
            if os.name == "nt":
                try:
                    os.rename(s_target, res)
                except OSError as exc:
                    if exc.errno != errno.EXDEV and getattr(exc, "winerror", None) != 17:
                        raise
                    _copy_to_new_path(s_target, res)
                    if s_target.is_dir():
                        shutil.rmtree(s_target)
                    else:
                        s_target.unlink()
            else:
                res = shutil.move(str(s_target), str(d_target))
            return ActionResult(success=True, message=f"Moved '{s_target.name}' to: {res}", output={"path": str(res)})
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
            res = d_target / s_target.name if s_target.is_file() and d_target.is_dir() else d_target
            if s_target.is_dir() and res.is_relative_to(s_target):
                return ActionResult(False, "A folder cannot be copied inside itself.", error="INVALID_DESTINATION")
            res.parent.mkdir(parents=True, exist_ok=True)
            _copy_to_new_path(s_target, res)
            return ActionResult(success=True, message=f"Copied '{s_target.name}' to: {res}", output={"path": str(res)})
        except FileExistsError:
            return ActionResult(False, "Destination already exists. Choose a new name.", error="PATH_EXISTS")
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
                lines = list(islice(f, max(0, max_lines)))
                content = "".join(lines)
            return ActionResult(
                success=True,
                message=f"Read {len(lines)} {'line' if len(lines) == 1 else 'lines'} from {target.name}.",
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
            if ".." in Path(pattern).parts or Path(pattern).is_absolute():
                return ActionResult(False, "Use a search pattern inside the selected directory.", error="INVALID_PATTERN")
            matches = []
            for p in target_dir.glob(pattern):
                if p.is_file() and p.resolve().is_relative_to(target_dir):
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
