"""Read-only setup checks: never print secrets or claim saved tokens are connected."""
from importlib.util import find_spec
from config import config
from .accounts import token_path


def setup_report():
    lines = ['ZENO setup check (no microphone recording or mailbox requests)']
    lines.append('Reasoning key: ' + ('configured; not validated' if config.GEMINI_API_KEY else 'missing; set GEMINI_API_KEY in .env'))
    lines.append(f'Voice: {config.TTS_VOICE} ({config.TTS_BACKEND}); online neural speech falls back to Windows voice.')
    lines.append(f'Speech recognition: {config.STT_BACKEND}; model {config.WHISPER_MODEL}')
    if config.STT_BACKEND == 'faster-whisper':
        if find_spec('faster_whisper') is None:
            lines.append('Local speech: install requirements-speech.txt, then run --setup-speech.')
        else:
            try:
                from voice.local_stt import load_model
                model = load_model()
                del model
                lines.append('Local speech: cached model loaded successfully; microphone not tested.')
            except Exception as exc:
                lines.append(f'Local speech: not ready ({type(exc).__name__}); run --setup-speech.')
    lines.append('Google online audio fallback: ' + ('enabled' if config.STT_ALLOW_ONLINE_FALLBACK else 'disabled'))
    for provider in ('gmail', 'outlook'):
        saved = token_path(provider).exists()
        lines.append(provider.title() + ': ' + ('saved sign-in exists; run --briefing to check access.' if saved else 'not connected; see docs/awareness.md for account setup.'))
    lines.append('Outlook app/client ID: ' + ('configured' if config.OUTLOOK_CLIENT_ID else 'missing'))
    lines.append('Windows/app notification access: run --briefing to test; notification access is not full chat access.')
    return '\n'.join(lines)
