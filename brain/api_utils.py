"""Bounded Gemini calls with explicit transport limits and safe diagnostics."""
import asyncio
import logging
import re
import time
from contextvars import ContextVar
from config import config

logger = logging.getLogger('VoiceAgent.API')
_last_failure = ContextVar('gemini_failure', default=None)


def last_api_failure():
    return _last_failure.get()


def classify_failure(exc):
    code = getattr(exc, 'code', None) or getattr(exc, 'status_code', None)
    match = re.search(r'\b(400|401|403|404|408|429|500|502|503|504)\b', str(exc))
    if code is None and match:
        code = int(match.group(1))
    if code in (401, 403):
        return 'authentication'
    if code == 429:
        return 'quota'
    if code == 404:
        return 'model'
    if code in (500, 502, 503, 504):
        return 'unavailable'
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or 'timeout' in type(exc).__name__.lower():
        return 'timeout'
    return 'request'


def reasoning_failure_message():
    kind = last_api_failure()
    if kind == 'authentication':
        return 'Google rejected the Gemini credentials. Check your API key and project access. No actions were run.'
    if kind == 'quota':
        return 'The Gemini project has reached a usage or rate limit. Check its quota before retrying. No actions were run.'
    if kind == 'model':
        return 'The configured Gemini models are unavailable to this project. Check the model setting. No actions were run.'
    if kind in {'unavailable', 'timeout'}:
        return 'Google Gemini is unavailable or taking too long to respond. Please retry shortly. No actions were run; direct commands such as check battery still work.'
    return 'I could not interpret that request. Please retry or use a direct command such as check battery. No actions were run.'


async def call_gemini_with_fallback(client, contents, primary_model=None, max_retries=2,
                                    initial_backoff=1.0, generation_config=None,
                                    timeout=12.0, total_timeout=36.0):
    """Bound the fallback chain and SDK retries; return None with a per-call diagnosis.

    A transport timeout also bounds the synchronous worker after asyncio times out.
    SDK retries are disabled so this wrapper owns retries and fallback decisions.
    """
    _last_failure.set(None)
    if client is None:
        return None
    primary = primary_model or config.GEMINI_MODEL
    models = list(dict.fromkeys([primary, *config.GEMINI_FALLBACK_MODELS]))
    deadline = time.monotonic() + total_timeout
    failures = []
    for model in models:
        for attempt in range(max_retries):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _last_failure.set('timeout')
                return None
            limit = min(timeout, remaining)
            if generation_config is None:
                request_config = {}
            elif isinstance(generation_config, dict):
                request_config = dict(generation_config)
            else:
                request_config = generation_config.model_dump(exclude_none=True)
            request_config['http_options'] = {
                # Gemini rejects transport deadlines below ten seconds.
                'timeout': max(10000, int(limit * 1000)),
                'retry_options': {'attempts': 1},
            }
            request_config.setdefault('automatic_function_calling', {'disable': True})
            try:
                response = await asyncio.wait_for(asyncio.to_thread(
                    client.models.generate_content, model=model, contents=contents,
                    config=request_config), timeout=limit)
                if response:
                    _last_failure.set(None)
                    return response
                failure = 'request'
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                failure = classify_failure(exc)
                # Log categories, never provider response bodies, keys or prompt contents.
                logger.warning('Gemini model %s failed: %s (attempt %s/%s)',
                               model, failure, attempt + 1, max_retries)
            failures.append(failure)
            _last_failure.set(failure)
            if failure == 'authentication':
                return None  # Another model cannot repair credentials.
            if failure not in {'timeout', 'unavailable', 'quota'} or attempt + 1 == max_retries:
                break
            wait = min(initial_backoff * 2 ** attempt, max(0, deadline - time.monotonic()))
            await asyncio.sleep(wait)
    if 'unavailable' in failures or 'timeout' in failures:
        _last_failure.set('unavailable')
    elif 'quota' in failures:
        _last_failure.set('quota')
    logger.error('Gemini fallback chain failed: %s', last_api_failure())
    return None
