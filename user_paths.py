"""Resolve Windows' configured user folders, including OneDrive redirection."""
import os
from pathlib import Path


def user_folder(name):
    names = {'desktop': ('Desktop', 'Desktop'), 'documents': ('Personal', 'Documents'),
             'downloads': ('{374DE290-123F-4565-9164-39C4925E467B}', 'Downloads')}
    value_name, fallback = names[name.lower()]
    if os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
                value, _ = winreg.QueryValueEx(key, value_name)
            path = Path(os.path.expandvars(value)).expanduser()
            if path.is_absolute():
                return path
        except (OSError, TypeError, ValueError):
            pass
    return Path.home() / fallback
