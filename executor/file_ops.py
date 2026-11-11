"""
File Operations for Voice Agent:
Safe file creation, deletion via Recycle Bin (send2trash), copy/move, search, and reading
with path validation against allowed user directories and system protection.
"""

import errno
import os
import shutil
import tempfile
import stat
from pathlib import Path
import logging
from typing import Optional, List, Dict, Any
from brain.planner import ActionResult
from config import BASE_DIR, config
from user_paths import user_folder
from .file_publication import stage_new_file

logger = logging.getLogger("VoiceAgent.FileOps")
MAX_READ_BYTES = 64 * 1024


def protected_tree(path, *, include_ancestors=False):
    for root in (BASE_DIR, config.DATA_DIR):
        root = root.resolve()
        if path.is_relative_to(root) or (include_ancestors and root.is_relative_to(path)):
            return True
    return False


def _verified_read_handle(stream, expected):
    info = os.fstat(stream.fileno())
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        return False
    if os.name == "nt":
        import msvcrt
        import win32file
        name = win32file.GetFinalPathNameByHandle(msvcrt.get_osfhandle(stream.fileno()), 0)
        if name.startswith("\\\\?\\UNC\\"):
            name = "\\\\" + name[8:]
        else:
            name = name.removeprefix("\\\\?\\")
        return Path(name) == expected
    return os.path.samestat(info, expected.stat())


def _private_path(path):
    # Reject Windows alternate streams and normalize DOS trailing dots/spaces.
    for part in path.parts[1:]:
        name = part.rstrip(" .").casefold()
        if (":" in name or name == ".env" or name.startswith((".env.", "client_secret"))
                or name in {".git", ".ssh", ".aws", "credentials.json", "google-client.json",
                            "token.json", "secrets.json", "paired_devices.json"}
                or name.endswith((".token", ".pem", ".key", ".pfx"))):
            return True
    if path.is_relative_to((config.DATA_DIR / "accounts").resolve()):
        return True
    # A hard link can disguise a credential file under an unrelated name.
    try:
        info = path.stat()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return stat.S_ISREG(info.st_mode) and info.st_nlink > 1


def _tree_is_safe(directory):
    def fail(error):
        raise error
    for parent, dirs, files in os.walk(directory, onerror=fail):
        for name in dirs + files:
            child = Path(parent) / name
            if (_private_path(child) or child.is_symlink() or
                    getattr(child.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                return False
    return True


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

    def _resolve_and_validate_path(self, path_str: str, *, tree=False) -> tuple[bool, Optional[Path], Optional[str]]:
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

        requested = Path(clean).expanduser().absolute()
        target = requested.resolve()
        if _private_path(requested) or _private_path(target):
            return False, None, "Access denied: this location is reserved for credentials."
        target_str = str(target).lower()
        settings = (config.DATA_DIR / 'app-access.json').resolve()
        if target == settings or (tree and target in settings.parents):
            return False, None, "App access settings can only be changed in the desktop dashboard."

        if protected_tree(target, include_ancestors=tree):
            return False, None, "ZENO's application and private data directories are protected."

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

        if tree and target.is_dir():
            try:
                if not _tree_is_safe(target):
                    return False, None, "Access denied: the folder contains protected files or links."
            except OSError:
                return False, None, "Could not safely inspect all files in this folder."
        return True, target, None

    def directory_listing(self, directory):
        valid, target, error = self._resolve_and_validate_path(directory)
        if not valid:
            return ActionResult(False, error, error="PATH_VALIDATION_FAILED")
        names = []
        try:
            with os.scandir(target) as entries:
                for index, entry in enumerate(entries):
                    if index >= 200:
                        names.append("... [listing limited]")
                        break
                    path = Path(entry.path)
                    allowed, _, _ = self._resolve_and_validate_path(str(path))
                    if allowed:
                        names.append(entry.name)
        except (OSError, ValueError):
            return ActionResult(False, "Directory listing failed.", error="DIRECTORY_UNAVAILABLE")
        output = "\n".join(names)[:2000]
        return ActionResult(True, output or "Empty directory.", output=output)

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
        valid, target, err = self._resolve_and_validate_path(path, tree=True)
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
        s_valid, s_target, s_err = self._resolve_and_validate_path(source, tree=True)
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
            valid, res, reason = self._resolve_and_validate_path(str(res))
            if not valid:
                return ActionResult(False, reason, error="DEST_PATH_ERROR")
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
        s_valid, s_target, s_err = self._resolve_and_validate_path(source, tree=True)
        if not s_valid or not s_target:
            return ActionResult(success=False, message=f"Source error: {s_err}", error="SOURCE_PATH_ERROR")

        d_valid, d_target, d_err = self._resolve_and_validate_path(destination)
        if not d_valid or not d_target:
            return ActionResult(success=False, message=f"Destination error: {d_err}", error="DEST_PATH_ERROR")

        if not s_target.exists():
            return ActionResult(success=False, message=f"Source not found: {s_target}", error="SOURCE_NOT_FOUND")

        try:
            res = d_target / s_target.name if s_target.is_file() and d_target.is_dir() else d_target
            valid, res, reason = self._resolve_and_validate_path(str(res))
            if not valid:
                return ActionResult(False, reason, error="DEST_PATH_ERROR")
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
            with target.open("rb") as f:
                if not _verified_read_handle(f, target):
                    return ActionResult(False, "The selected file changed. Select it again.", error="FILE_CHANGED")
                data = f.read(MAX_READ_BYTES + 1)
            limited = len(data) > MAX_READ_BYTES
            preview = data[:MAX_READ_BYTES].decode("utf-8", errors="replace")
            lines = preview.replace("\r\n", "\n").replace("\r", "\n").splitlines(keepends=True)
            limit = min(200, max(0, max_lines))
            limited = limited or len(lines) > limit
            lines = lines[:limit]
            content = "".join(lines)
            return ActionResult(
                success=True,
                message=f"Read {len(lines)} {'line' if len(lines) == 1 else 'lines'} from {target.name}."
                        + (" Preview truncated." if limited else ""),
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
                if (p.is_file() and not protected_tree(p.resolve()) and not _private_path(p) and not _private_path(p.resolve())
                        and p.resolve().is_relative_to(target_dir)):
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
