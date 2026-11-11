"""Online neural speech with bounded generation and interruptible local playback."""
import asyncio
import os
from pathlib import Path
import tempfile
import time

from config import config


async def render_speech(text, path):
    if config.TTS_BACKEND == "elevenlabs":
        import httpx
        from urllib.parse import quote
        if not config.ELEVENLABS_API_KEY or not config.TTS_VOICE:
            raise ValueError("ElevenLabs requires an API key and a voice ID.")
        url = "https://api.elevenlabs.io/v1/text-to-speech/" + quote(config.TTS_VOICE, safe="")
        async with httpx.AsyncClient(timeout=20) as client:
            response = await asyncio.wait_for(client.post(
                url, headers={"xi-api-key": config.ELEVENLABS_API_KEY, "Accept": "audio/mpeg"},
                params={"output_format": "mp3_44100_128"},
                json={"text": text, "model_id": "eleven_multilingual_v2"},
            ), timeout=20)
            response.raise_for_status()
            if not response.content or not response.headers.get("content-type", "").startswith("audio/"):
                raise ValueError("ElevenLabs returned no playable audio.")
            path.write_bytes(response.content)
        return
    import edge_tts
    communication = edge_tts.Communicate(text, config.TTS_VOICE, rate=config.TTS_RATE,
                                        volume=config.TTS_VOLUME, pitch=config.TTS_PITCH)
    await asyncio.wait_for(communication.save(str(path)), timeout=20)


def speak_neural(text, running):
    os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
    import pygame
    with tempfile.TemporaryDirectory(prefix='zeno-speech-') as folder:
        path = Path(folder) / 'speech.mp3'
        async def render_until_cancelled():
            task = asyncio.create_task(render_speech(text, path))
            try:
                while not task.done():
                    if not running():
                        return
                    await asyncio.wait({task}, timeout=0.05)
                await task
            finally:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        asyncio.run(render_until_cancelled())
        if not running():
            return
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy() and running():
                time.sleep(0.05)
        finally:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
