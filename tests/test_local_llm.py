import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from brain import api_utils, local_llm
from config import config


@pytest.mark.asyncio
@pytest.mark.parametrize('mode,confirmed', [('local', True), ('free-cloud-local', False), ('invalid', True)])
async def test_cloud_never_called_without_both_gates(monkeypatch, mode, confirmed):
    monkeypatch.setattr(config, 'LLM_MODE', mode)
    monkeypatch.setattr(config, 'GEMINI_FREE_TIER_CONFIRMED', confirmed)
    monkeypatch.setattr(config, 'LOCAL_LLM_ENABLED', True)
    local = AsyncMock(return_value=SimpleNamespace(text='local answer'))
    monkeypatch.setattr(local_llm, 'generate_local', local)
    cloud = MagicMock()
    response = await api_utils.call_gemini_with_fallback(cloud, 'hello')
    assert response.text == 'local answer'
    cloud.models.generate_content.assert_not_called()
    local.assert_awaited_once()


@pytest.mark.asyncio
async def test_quota_immediately_falls_back_to_local(monkeypatch):
    monkeypatch.setattr(config, 'LOCAL_LLM_ENABLED', True)
    local = AsyncMock(return_value=SimpleNamespace(text='local'))
    monkeypatch.setattr(local_llm, 'generate_local', local)
    cloud = MagicMock()
    cloud.models.generate_content.side_effect = Exception('429 quota')
    response = await api_utils.call_gemini_with_fallback(cloud, 'hello')
    assert response.text == 'local'
    assert cloud.models.generate_content.call_count == 1
    assert api_utils.last_api_failure() is None


@pytest.mark.asyncio
async def test_empty_cloud_response_uses_local(monkeypatch):
    monkeypatch.setattr(config, 'LOCAL_LLM_ENABLED', True)
    monkeypatch.setattr(config, 'GEMINI_FALLBACK_MODELS', [])
    monkeypatch.setattr(local_llm, 'generate_local', AsyncMock(return_value=SimpleNamespace(text='local')))
    cloud = MagicMock()
    cloud.models.generate_content.return_value = SimpleNamespace(text='')
    result = await api_utils.call_gemini_with_fallback(cloud, 'hello')
    assert result.text == 'local'


@pytest.mark.asyncio
async def test_paid_models_and_hosted_tools_never_sent(monkeypatch):
    monkeypatch.setattr(config, 'GEMINI_FALLBACK_MODELS', ['gemini-3.8-flash'])
    cloud = MagicMock()
    cloud.models.generate_content.return_value = SimpleNamespace(text='answer')
    await api_utils.call_gemini_with_fallback(cloud, 'hello', primary_model='paid-model',
        generation_config={'tools': [{'google_search': {}}], 'cached_content': 'cache',
                           'response_mime_type': 'application/json'})
    sent = cloud.models.generate_content.call_args.kwargs
    assert sent['model'] == 'gemini-3.8-flash'
    assert 'tools' not in sent['config'] and 'cached_content' not in sent['config']


@pytest.mark.asyncio
async def test_local_failure_and_vision_are_honest(monkeypatch):
    monkeypatch.setattr(config, 'LLM_MODE', 'local')
    monkeypatch.setattr(config, 'LOCAL_LLM_ENABLED', True)
    generate = AsyncMock(side_effect=ConnectionError())
    monkeypatch.setattr(local_llm, 'generate_local', generate)
    assert await api_utils.call_gemini_with_fallback(None, 'hello') is None
    assert api_utils.last_api_failure() == 'local'
    generate.reset_mock()
    assert await api_utils.call_gemini_with_fallback(None, [object(), 'image']) is None
    assert api_utils.last_api_failure() == 'local_vision'
    generate.assert_not_awaited()


def mock_transport(monkeypatch, handler):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(local_llm.httpx, 'AsyncClient',
                        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))


@pytest.mark.asyncio
async def test_local_payload_preserves_instructions_and_json_schema(monkeypatch):
    import json
    requests = []
    def handler(request):
        requests.append(request)
        if request.url.path == '/api/show':
            return httpx.Response(200, json={'capabilities': ['completion']})
        return httpx.Response(200, json={'done': True, 'response': '{"kind":"chat"}'})
    mock_transport(monkeypatch, handler)
    response = await local_llm.generate_local('request', {'system_instruction': 'rules',
        'response_mime_type': 'application/json', 'response_schema': {
            'type': 'OBJECT', 'properties': {'kind': {'type': 'STRING'}}, 'required': ['kind']}})
    sent = json.loads(requests[-1].content)
    assert str(requests[-1].url) == 'http://127.0.0.1:11434/api/generate'
    assert sent['system'] == 'rules' and sent['prompt'] == 'request\n/no_think'
    assert sent['format']['properties']['kind']['type'] == 'string'
    assert sent['think'] is False and sent['stream'] is False
    assert response.provider == 'ollama'


@pytest.mark.asyncio
async def test_local_cloud_alias_rejected_before_prompt(monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={'remote_host': 'https://ollama.com', 'remote_model': 'cloud'})
    mock_transport(monkeypatch, handler)
    with pytest.raises(ValueError, match='Cloud-backed'):
        await local_llm.generate_local('private request')
    assert len(requests) == 1 and b'private request' not in requests[0].content


@pytest.mark.asyncio
async def test_local_cancel_propagates(monkeypatch):
    monkeypatch.setattr(config, 'LLM_MODE', 'local')
    monkeypatch.setattr(config, 'LOCAL_LLM_ENABLED', True)
    monkeypatch.setattr(local_llm, 'generate_local', AsyncMock(side_effect=asyncio.CancelledError))
    with pytest.raises(asyncio.CancelledError):
        await api_utils.call_gemini_with_fallback(None, 'cancel')


@pytest.mark.asyncio
@pytest.mark.parametrize('body', [{'done': False, 'response': 'partial'},
    {'done': True, 'done_reason': 'length', 'response': 'cut off'}, {'done': True, 'response': ''}])
async def test_incomplete_local_output_rejected(monkeypatch, body):
    mock_transport(monkeypatch, lambda request: httpx.Response(200, json=(
        {} if request.url.path == '/api/show' else body)))
    with pytest.raises(ValueError, match='incomplete'):
        await local_llm.generate_local('hello')


@pytest.mark.asyncio
@pytest.mark.parametrize('text', ['<think>internal reasoning</think>Final answer.',
                                'internal reasoning</think>Final answer.'])
async def test_local_only_returns_final_answer(monkeypatch, text):
    mock_transport(monkeypatch, lambda request: httpx.Response(200, json=(
        {} if request.url.path == '/api/show' else {'done': True, 'response': text})))
    response = await local_llm.generate_local('hello')
    assert response.text == 'Final answer.'


@pytest.mark.asyncio
async def test_brain_routes_locally_without_a_cloud_client(monkeypatch, tmp_path):
    from brain.zeno_brain import ZenoBrain
    monkeypatch.setattr(config, 'LLM_MODE', 'local')
    monkeypatch.setattr(config, 'LOCAL_LLM_ENABLED', True)
    monkeypatch.setattr(config, 'MEMORY_FILE', str(tmp_path / 'memory.json'))
    local = AsyncMock(return_value=SimpleNamespace(text='{"kind":"chat","message":"RAM holds active data."}'))
    monkeypatch.setattr(local_llm, 'generate_local', local)
    brain = ZenoBrain(api_key='not-used')
    assert brain.client is None and brain.nlu.client is None
    response = await brain.think('Explain RAM without opening any apps')
    assert response.kind == 'chat' and not response.actions
    local.assert_awaited_once()


def test_runtime_does_not_start_when_disabled(monkeypatch):
    from brain import ollama_runtime
    monkeypatch.setattr(config, 'LOCAL_LLM_ENABLED', False)
    launch = MagicMock()
    monkeypatch.setattr(ollama_runtime.subprocess, 'Popen', launch)
    assert not ollama_runtime.start_local_runtime()
    launch.assert_not_called()


@pytest.mark.asyncio
async def test_local_http_has_total_deadline(monkeypatch):
    monkeypatch.setattr(config, 'OLLAMA_TIMEOUT_SECONDS', 0.01)
    async def slow(request):
        await asyncio.sleep(1)
        return httpx.Response(200, json={})
    mock_transport(monkeypatch, slow)
    with pytest.raises(TimeoutError):
        await local_llm.generate_local('hello')


def test_cloud_client_pins_developer_api(monkeypatch):
    from google import genai
    from brain.nlu import NLUEngine
    client = MagicMock()
    monkeypatch.setattr(genai, 'Client', client)
    NLUEngine(api_key='synthetic-key')
    options = client.call_args.kwargs
    assert options['vertexai'] is False and options['enterprise'] is False
    assert options['http_options']['base_url'] == 'https://generativelanguage.googleapis.com'


@pytest.mark.asyncio
async def test_update_summary_uses_local_without_cloud_client(monkeypatch):
    from awareness.service import AwarenessService
    monkeypatch.setattr(config, 'LLM_MODE', 'local')
    monkeypatch.setattr(config, 'LOCAL_LLM_ENABLED', True)
    local = AsyncMock(return_value=SimpleNamespace(text='Synthetic reminder summary.'))
    monkeypatch.setattr(local_llm, 'generate_local', local)
    service = AwarenessService.__new__(AwarenessService)
    service.store = MagicMock()
    service.store.events.return_value = [{'id': 'synthetic', 'title': 'Example reminder'}]
    service.status = {}
    service._remember_briefing = MagicMock()
    assert await service.summarize(None) == 'Synthetic reminder summary.'
    local.assert_awaited_once()
