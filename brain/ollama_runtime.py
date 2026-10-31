"""Start an already-installed local Ollama server on Windows, without downloads."""
import os
from pathlib import Path
import shutil
import socket
import subprocess

from config import config


def start_local_runtime():
    if not config.LOCAL_LLM_ENABLED or os.name != 'nt':
        return False
    try:
        with socket.create_connection(('127.0.0.1', 11434), timeout=0.2):
            return True
    except OSError:
        pass
    local = Path(os.environ.get('LOCALAPPDATA', ''))
    candidates = [local / 'ZENO/ollama/ollama.exe',
                  local / 'Programs/Ollama/ollama.exe']
    executable = next((str(path) for path in candidates if path.is_file()), None)
    executable = executable or shutil.which('ollama')
    if not executable:
        return False
    env = dict(os.environ, OLLAMA_HOST='127.0.0.1:11434', OLLAMA_NO_CLOUD='1')
    try:
        subprocess.Popen([executable, 'serve'], env=env, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    except OSError:
        return False
    return True
