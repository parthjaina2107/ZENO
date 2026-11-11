"""Local activity records and optional age-based cleanup for generated files."""
from datetime import date
import logging
import re
import stat
import time

from config import config


def audit_path():
    return config.DATA_DIR / "audit" / (date.today().isoformat() + ".jsonl")


def audit_files():
    directory = config.DATA_DIR / "audit"
    if directory.is_dir():
        yield from sorted((path for path in directory.iterdir()
                           if re.fullmatch(r"\d{4}-\d\d-\d\d\.jsonl", path.name) and path.is_file()), reverse=True)


def prune_history():
    if config.HISTORY_RETENTION_DAYS <= 0:
        return
    cutoff = time.time() - config.HISTORY_RETENTION_DAYS * 86400
    patterns = {"audit": r"\d{4}-\d\d-\d\d\.jsonl", "task_reports": r"task_[a-f0-9]{32}\.json",
                "screenshots": r"screenshot_\d{8}_\d{6}(?:_\d{6})?\.png"}
    for folder, pattern in patterns.items():
        directory = config.DATA_DIR / folder
        try:
            if not directory.is_dir() or directory.resolve().parent != config.DATA_DIR.resolve():
                continue
            for path in directory.iterdir():
                if not re.fullmatch(pattern, path.name):
                    continue
                info = path.lstat()
                if (stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_mtime < cutoff
                        and not getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                    path.unlink(missing_ok=True)
        except OSError:
            logging.getLogger(__name__).warning("Could not finish history cleanup in %s", folder)
