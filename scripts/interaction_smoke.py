"""Optional live Gemini check; execution is restricted to read-only system info."""
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brain.zeno_brain import ZenoBrain
from brain.memory import ZenoMemory
from brain.interaction import outcome_reply
from brain.task_runner import TaskRunner
from executor.task_executor import TaskExecutor
from executor.permissions import PermissionManager
from config import config


async def main():
    brain = ZenoBrain(executor=TaskExecutor())
    brain.memory = ZenoMemory(str(config.BASE_DIR / 'scratch' / 'interaction-smoke-memory.json'))
    print('Reasoning configured:', bool(brain.client), 'Model:', config.GEMINI_MODEL, flush=True)
    for text, expected in [
        ('Why does my laptop restart randomly?', 'chat'),
        ('Write a short poem about rain in Notepad', 'task'),
    ]:
        response = await brain.think(text)
        print('INPUT:', text, '\nROUTE:', response.kind, '\nREPLY:', response.message, flush=True)
        assert response.kind == expected, (expected, response.kind)
    brain.memory.clear_short_term()
    response = await brain.think('Check my battery and tell me the current time')
    assert response.kind == 'task', response

    async def deny(action):
        raise AssertionError('Read-only check must not need approval')

    async def progress(message):
        pass

    runner = TaskRunner(brain, PermissionManager(), max_steps=5)
    original_preflight = runner.preflight

    def read_only(action):
        assert action.action_type == 'system_info', action.action_type
        original_preflight(action)

    runner.preflight = read_only
    report = await runner.run(response.message, deny, progress)
    print('STATUS:', report.status, flush=True)
    print('SPOKEN:', await outcome_reply(brain, 'Check my battery and tell me the current time',
                                       report.steps, report.status, report.message), flush=True)
    assert report.status == 'completed', report.message
    assert len(report.steps) == 2, report.steps
    # Follow-up must see observations, not just the original requested action.
    followup = await brain.think('What was my battery percentage just now?')
    print('FOLLOW-UP:', followup.kind, followup.message, flush=True)
    assert followup.kind == 'chat', followup
    print('LIVE CHECK PASSED', flush=True)


if __name__ == '__main__':
    asyncio.run(main())
