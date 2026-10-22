"""Bounded PCM capture, with cancellation checked between microphone buffers."""
import math
import struct
import time
from collections import deque


def rms(data):
    samples = struct.unpack("<" + "h" * (len(data) // 2), data)
    return math.sqrt(sum(sample * sample for sample in samples) / max(1, len(samples)))


def capture(control, device=None, wait_seconds=15, phrase_seconds=25):
    import speech_recognition as sr
    control.check()
    # Construct/open only after explicit activation. The context closes on ALL exits.
    with sr.Microphone(device_index=device, sample_rate=16000, chunk_size=512) as source:
        control.check()
        started = time.monotonic()
        speech_started = None
        last_voice = started
        frames = []
        preroll = deque(maxlen=8)
        threshold = 300.0
        while True:
            control.check()
            chunk = source.stream.read(source.CHUNK)
            if not chunk:
                raise RuntimeError("The microphone stopped providing audio. Check your input device.")
            now = time.monotonic()
            level = rms(chunk)
            if speech_started is None:
                preroll.append(chunk)
                if level > threshold:
                    speech_started = last_voice = now
                    frames.extend(preroll)
                elif now - started >= wait_seconds:
                    return None
                else:
                    threshold = max(250.0, min(1500.0, threshold * 0.98 + level * 1.8 * 0.02))
            else:
                frames.append(chunk)
                if level > threshold:
                    last_voice = now
                if now - last_voice >= 0.9 or now - speech_started >= phrase_seconds:
                    break
        control.check()
        return sr.AudioData(b"".join(frames), source.SAMPLE_RATE, source.SAMPLE_WIDTH)
