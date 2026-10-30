"""Bounded PCM capture, with cancellation checked between microphone buffers."""
import math
import struct
import time
from collections import deque
from contextlib import ExitStack


def rms(data):
    samples = struct.unpack("<" + "h" * (len(data) // 2), data)
    return math.sqrt(sum(sample * sample for sample in samples) / max(1, len(samples)))


def capture(control, device=None, wait_seconds=15, phrase_seconds=25, pause_seconds=0.6, on_level=None,
            on_open=None, on_close=None):
    import speech_recognition as sr
    control.check()
    # Construct/open only after explicit activation. The context closes on ALL exits.
    with ExitStack() as stack:
        if on_close:
            stack.callback(on_close)
        source = stack.enter_context(sr.Microphone(device_index=device, sample_rate=16000, chunk_size=512))
        control.check()
        if on_open:
            on_open()
        started = time.monotonic()
        speech_started = None
        last_voice = started
        frames = []
        preroll = deque(maxlen=8)
        threshold = 300.0
        last_meter = 0.0
        while True:
            control.check()
            chunk = source.stream.read(source.CHUNK)
            if not chunk:
                raise RuntimeError("The microphone stopped providing audio. Check your input device.")
            now = time.monotonic()
            level = rms(chunk)
            if on_level and now - last_meter >= 0.05:
                on_level(min(1.0, level / 4000.0))
                last_meter = now
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
                if now - last_voice >= pause_seconds or now - speech_started >= phrase_seconds:
                    break
        control.check()
        return sr.AudioData(b"".join(frames), source.SAMPLE_RATE, source.SAMPLE_WIDTH)
