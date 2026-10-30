from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from brain.api_utils import call_gemini_with_fallback, last_api_failure, reasoning_failure_message
from config import config


@pytest.mark.asyncio
async def test_provider_failure_is_specific_and_transport_retries_are_bounded(monkeypatch):
    monkeypatch.setattr(config, 'GEMINI_FALLBACK_MODELS', ['fallback'])
    client = MagicMock()
    client.models.generate_content.side_effect = Exception('503 UNAVAILABLE provider overloaded')
    original = {'response_mime_type': 'application/json'}
    assert await call_gemini_with_fallback(client, 'prompt', primary_model='primary',
                                          max_retries=1, generation_config=original) is None
    assert last_api_failure() == 'unavailable'
    assert 'Google Gemini' in reasoning_failure_message()
    assert 'No actions were run' in reasoning_failure_message()
    assert client.models.generate_content.call_count == 2
    for call in client.models.generate_content.call_args_list:
        assert call.kwargs['config']['http_options']['retry_options']['attempts'] == 1
        assert 10000 <= call.kwargs['config']['http_options']['timeout'] <= 12000
    assert original == {'response_mime_type': 'application/json'}


@pytest.mark.asyncio
async def test_authentication_stops_without_wasting_fallback_requests():
    client = MagicMock()
    client.models.generate_content.side_effect = Exception('403 PERMISSION_DENIED')
    assert await call_gemini_with_fallback(client, 'prompt') is None
    assert client.models.generate_content.call_count == 1
    assert last_api_failure() == 'authentication'
    assert 'credentials' in reasoning_failure_message()
    client.models.generate_content.side_effect = None
    client.models.generate_content.return_value = SimpleNamespace(text='OK')
    assert (await call_gemini_with_fallback(client, 'prompt')).text == 'OK'
    assert last_api_failure() is None


@pytest.mark.asyncio
async def test_entire_fallback_chain_has_a_deadline(monkeypatch):
    import time
    monkeypatch.setattr(config, 'GEMINI_FALLBACK_MODELS', ['second', 'third'])
    client = MagicMock()
    def slow(**kwargs):
        time.sleep(0.1)
        return SimpleNamespace(text='late')
    client.models.generate_content.side_effect = slow
    assert await call_gemini_with_fallback(client, 'prompt', timeout=0.02,
                                          total_timeout=0.015) is None
    assert client.models.generate_content.call_count == 1
    assert last_api_failure() == 'timeout'
