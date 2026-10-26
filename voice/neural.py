"""Online neural speech with bounded generation and interruptible local playback."""
import asyncio
import os
from pathlib import Path
import tempfile
import time

from config import config


async def render_speech(text, path):
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
