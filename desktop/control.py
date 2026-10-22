"""Cooperative cancellation: stop future work, drain already-started OS calls."""
import asyncio
import threading


class RunControl:
    def __init__(self):
        self.cancelled = threading.Event()
        self._lock = threading.Lock()

    def cancel(self):
        with self._lock:
            self.cancelled.set()

    def immediate(self, function, *args):
        """Atomically enqueue short work against cancellation (never OS calls)."""
        with self._lock:
            self.check()
            return function(*args)

    def check(self):
        if self.cancelled.is_set():
            raise asyncio.CancelledError()

    async def wait(self, awaitable):
        """Interrupt reasoning/approval waits. Never use this for OS mutations."""
        task = asyncio.ensure_future(awaitable)
        try:
            while not task.done():
                self.check()
                await asyncio.wait({task}, timeout=0.05)
            self.check()
            return task.result()
        finally:
            if not task.done():
                task.cancel()
            # Retrieve errors and finish async cleanup, including on cancellation.
            await asyncio.gather(task, return_exceptions=True)

    async def call(self, function, *args):
        """Do not abandon a thread that could still change the user's system."""
        def guarded():
            self.check()
            return function(*args)
        self.check()
        return await asyncio.to_thread(guarded)
