"""Compare installed program files with the Git checkout under test."""
import hashlib
from pathlib import Path
import subprocess
import sys

root, installed = map(Path, sys.argv[1:])
paths = ("awareness", "brain", "desktop", "executor", "server", "tunnel", "voice",
         "app_access.py", "config.py", "main.py", "user_paths.py", ".env.example",
         "Start-ZENO.cmd", "LICENSE", "requirements*.txt")
entries = subprocess.check_output(["git", "-C", str(root), "ls-files", "-s", "-z", "--", *paths])


def blob_hash(content):
    return hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()


for row in entries.rstrip(b"\0").split(b"\0"):
    metadata, name = row.split(b"\t", 1)
    path = installed / name.decode("utf-8")
    data = path.read_bytes()
    expected = metadata.split()[1].decode("ascii")
    if blob_hash(data) != expected:
        if b"\0" in data or blob_hash(data.replace(b"\r\n", b"\n")) != expected:
            raise SystemExit(f"Installer differs from source: {path.name}")
print("Installed program files match Git.")
