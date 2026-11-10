"""Read the current Windows media session for the island."""
import asyncio
import threading
from datetime import datetime, timezone

from PySide6.QtCore import QObject, Signal

import app_access


async def read_playback():
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
    timeline = session.get_timeline_properties()
    playing = playback.playback_status == Status.PLAYING
    duration = (timeline.end_time - timeline.start_time).total_seconds()
    position = (timeline.position - timeline.start_time).total_seconds()
    if playing and duration > 0 and timeline.last_updated_time.year > 1970:
        age = (datetime.now(timezone.utc) - timeline.last_updated_time).total_seconds()
        rate = playback.playback_rate
        position += max(0, age) * (getattr(rate, 'value', rate) if rate is not None else 1)
    return (properties.title, properties.artist, playing,
            int(max(0, min(position, duration))), int(max(0, duration)))


class MediaMonitor(QObject):
    changed = Signal(object)

    def __init__(self, parent):
        super().__init__(parent)
        self.stopped = threading.Event()
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
        while not self.stopped.is_set():
            current = None
            if app_access.allowed('media'):
                try:
                    current = asyncio.run(asyncio.wait_for(read_playback(), timeout=3))
                except (ImportError, OSError, RuntimeError, TimeoutError):
                    pass
                if not app_access.allowed('media'):
                    current = None
            if current != previous and not self.stopped.is_set():
                self.changed.emit(current)
                previous = current
            self.stopped.wait(1)
