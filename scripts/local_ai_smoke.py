"""Explicit local-model smoke check: synthetic text, no tools, mic or cloud calls."""
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import config
from brain.api_utils import call_gemini_with_fallback, reasoning_failure_message
from brain.interaction import route_request


async def main():
    config.LLM_MODE = 'local'
    config.GEMINI_FREE_TIER_CONFIRMED = False
    config.LOCAL_LLM_ENABLED = True
    answer = await call_gemini_with_fallback(None, 'Reply in one short sentence: what is 2 plus 2?')
    if answer is None:
        print(reasoning_failure_message())
        return 1
    print('Local model:', config.OLLAMA_MODEL)
    print('Text response:', answer.text)
    memory = SimpleNamespace(get_recent_history=lambda **kwargs: [], get_all_facts=lambda: {})
    brain = SimpleNamespace(client=None, memory=memory)
    from brain.nlu import NLUEngine
    brain.nlu = NLUEngine(api_key='')
    result = await route_request(brain, 'Explain what RAM does. Do not open any apps.')
    if result['kind'] != 'chat':
        raise RuntimeError('Synthetic conversational request was incorrectly routed as an action')
    print('Structured routing:', result['kind'])
    from brain.task_runner import TaskRunner
    from brain.planner import validate_action_params
    decision = await TaskRunner(brain, None).decide('Check the battery percentage.', [])
    params, error = validate_action_params(decision.get('action'), decision.get('parameters'))
    if decision.get('action') != 'system_info' or error or params.get('type') != 'battery':
        raise RuntimeError('Synthetic battery request did not produce the expected validated plan')
    print('Task planning: valid system_info/battery action (not executed).')
    print('Passed: local text, structured routing and planning; no actions executed.')
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
