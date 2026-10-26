"""Optional live Gemini check: opens Notepad and writes a new scratch report."""
import asyncio
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
load_dotenv(Path(os.getenv("LOCALAPPDATA", "")) / "ZENO" / ".env")

from brain.zeno_brain import ZenoBrain
from brain.task_runner import TaskRunner
from executor.task_executor import TaskExecutor
from executor.permissions import PermissionManager


async def run():
    path = ROOT / "scratch" / f"task_smoke_{uuid.uuid4().hex}.txt"
    goal = f'Open Notepad, create the file {path} with exactly this text: "ZENO task engine test." Then read that file back to verify the saved text.'
    async def deny(action):
        return False
    async def progress(message):
        print(message, flush=True)
    report = await TaskRunner(ZenoBrain(executor=TaskExecutor()), PermissionManager()).run(goal, deny, progress)
    print(report.summary(), flush=True)
    print("Report:", report.report_path, flush=True)
    required = {"open_app", "file_create", "file_read"}
    return report.status == "completed" and required.issubset({step["action"] for step in report.steps}) and path.exists() and path.read_text() == "ZENO task engine test."


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run()) else 1)
