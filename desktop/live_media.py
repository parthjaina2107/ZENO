"""Read the current Windows media session for the island."""
import asyncio
import threading
from queue import Empty, SimpleQueue
from datetime import datetime, timezone

from PySide6.QtCore import QObject, Signal

import app_access


async def thumbnail(reference):
    if reference is None:
        return None
    from winrt.windows.storage.streams import DataReader
    stream = await reference.open_read_async()
    try:
        if not 0 < stream.size <= 4 * 1024 * 1024:
            return None
        reader = DataReader(stream)
        try:
            size = await reader.load_async(stream.size)
            data = bytearray(size)
            reader.read_bytes(data)
            return bytes(data)
        finally:
            reader.detach_stream()
            reader.close()
    finally:
        stream.close()


async def read_playback(cache, pending):
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as Manager,
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status,
    )
    session = (await Manager.request_async()).get_current_session()
    if session is None:
        return None
    playback = session.get_playback_info()
    if playback.playback_status not in (Status.PLAYING, Status.PAUSED):
        return None
    properties = await session.try_get_media_properties_async()
    if not properties.title:
        return None
    key = (session.source_app_user_model_id, properties.title, properties.artist)
    methods = {'previous': session.try_skip_previous_async, 'next': session.try_skip_next_async,
               'play': session.try_play_async, 'pause': session.try_pause_async}
    if pending and pending[0] == key and app_access.allowed('media'):
        await methods[pending[1]]()
        playback = session.get_playback_info()
    if cache.get('key') != key:
        cache.clear()
        try:
            cache['art'] = await asyncio.wait_for(thumbnail(properties.thumbnail), timeout=1)
        except (OSError, RuntimeError, TimeoutError, ImportError, ValueError):
            pass
        cache['key'] = key
    controls = playback.controls
    timeline = session.get_timeline_properties()
    playing = playback.playback_status == Status.PLAYING
    duration = (timeline.end_time - timeline.start_time).total_seconds()
    position = (timeline.position - timeline.start_time).total_seconds()
    if playing and duration > 0 and timeline.last_updated_time.year > 1970:
        age = (datetime.now(timezone.utc) - timeline.last_updated_time).total_seconds()
        rate = playback.playback_rate
        position += max(0, age) * (getattr(rate, 'value', rate) if rate is not None else 1)
    return (properties.title, properties.artist, playing,
            int(max(0, min(position, duration))), int(max(0, duration)), cache.get('art'),
            (controls.is_previous_enabled, controls.is_pause_enabled,
             controls.is_play_enabled, controls.is_next_enabled), key)


class MediaMonitor(QObject):
    changed = Signal(object)

    def __init__(self, parent):
        super().__init__(parent)
        self.stopped = threading.Event()
        self.commands = SimpleQueue()
        self.worker = threading.Thread(target=self.poll, daemon=True, name='ZENO media session')

    def poll(self):
        from winrt.runtime import init_apartment, uninit_apartment, ApartmentType
        init_apartment(ApartmentType.MULTI_THREADED)
        try:
            self.poll_sessions()
        finally:
            uninit_apartment()

    def poll_sessions(self):
        previous = None
        cache = {}
        while not self.stopped.is_set():
            current = None
            try:
                pending = self.commands.get_nowait()
            except Empty:
                pending = None
            if app_access.allowed('media'):
                try:
                    current = asyncio.run(asyncio.wait_for(read_playback(cache, pending), timeout=3))
                except (ImportError, OSError, RuntimeError, TimeoutError):
                    pass
                if not app_access.allowed('media'):
                    current = None
            if current is None:
                cache.clear()
            if current != previous and not self.stopped.is_set():
                self.changed.emit(current)
                previous = current
            self.stopped.wait(1)
