"""Local-only Ollama transport; no downloads, cloud models or tool execution."""
import asyncio
import base64
from types import SimpleNamespace

import httpx

import app_access
from config import config

OLLAMA_URL = 'http://127.0.0.1:11434'


def _schema(value):
    """Translate Gemini's uppercase schema types into JSON Schema types."""
    if isinstance(value, dict):
        return {key: item.lower() if key == 'type' and isinstance(item, str)
                else _schema(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_schema(item) for item in value]
    return value


async def generate_local(contents, generation_config=None, *, image_bytes=None):
    # A text-only model must never pretend to have inspected an image.
    if not isinstance(contents, str):
        raise ValueError('Local text model does not support image inputs')
    if not app_access.allowed("local_ai"):
        raise ValueError(app_access.denial("local_ai"))
    model = config.OLLAMA_VISION_MODEL if image_bytes is not None else config.OLLAMA_MODEL
    if not model or 'cloud' in model.lower() or '/' in model or '\\' in model:
        raise ValueError('Select a downloaded local Ollama model')
    options = generation_config or {}
    if not isinstance(options, dict):
        options = options.model_dump(exclude_none=True)
    payload = {
        'model': model, 'prompt': contents + ('\n/no_think' if model.startswith('qwen3:') else ''),
        'stream': False, 'think': False,
        'keep_alive': '5m',
        'options': {'num_ctx': 8192, 'num_predict': 1024, 'temperature': 0.2},
    }
    if options.get('system_instruction'):
        payload['system'] = options['system_instruction']
    if options.get('response_mime_type') == 'application/json':
        payload['format'] = _schema(options.get('response_schema') or 'json')
    # Fixed loopback origin, no proxies or redirects. A local server can still
    # expose cloud aliases, so check the installed model metadata before use.
    async with asyncio.timeout(config.OLLAMA_TIMEOUT_SECONDS):
        async with httpx.AsyncClient(base_url=OLLAMA_URL, trust_env=False,
                                    follow_redirects=False,
                                    timeout=config.OLLAMA_TIMEOUT_SECONDS) as client:
            info = await client.post('/api/show', json={'model': model})
            info.raise_for_status()
            metadata = info.json()
            if metadata.get('remote_host') or metadata.get('remote_model'):
                raise ValueError('Cloud-backed Ollama models are disabled')
            if image_bytes is not None:
                if 'vision' not in metadata.get('capabilities', []):
                    raise ValueError('The selected model cannot interpret images')
                payload['images'] = [base64.b64encode(image_bytes).decode('ascii')]
            response = await client.post('/api/generate', json=payload)
            response.raise_for_status()
            result = response.json()
            text = result.get('response')
            if isinstance(text, str):
                # Some local runners leave Qwen's reasoning delimiter in response
                # instead of separating it into the thinking field. Never speak it.
                if '</think>' in text:
                    text = text.rsplit('</think>', 1)[1]
                if '<think>' in text:
                    raise ValueError('Local model did not finish its answer')
                text = text.strip()
            if not result.get('done') or result.get('done_reason') == 'length' or not isinstance(text, str) or not text.strip():
                raise ValueError('Local model returned an incomplete or empty response')
            return SimpleNamespace(text=text, provider='ollama', model=model)
