"""Thread-sicherer Ereignisbus für die Live-Aktualisierung des Cockpits (SSE).

Der Service ist synchron und läuft im Threadpool, die SSE-Verbindungen leben im Event-Loop.
publish() darf deshalb aus jedem Thread aufgerufen werden.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = set()

    def publish(self, event: dict) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
        for loop, queue in subscribers:
            try:
                loop.call_soon_threadsafe(self._offer, queue, event)
            except RuntimeError:  # Loop bereits geschlossen
                pass

    @staticmethod
    def _offer(queue: asyncio.Queue, event: dict) -> None:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass  # "changed"-Signale lassen sich zusammenfassen, ein volles Postfach reicht dem Client

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=8)
        entry = (asyncio.get_running_loop(), queue)
        with self._lock:
            self._subscribers.add(entry)
        try:
            yield queue
        finally:
            with self._lock:
                self._subscribers.discard(entry)

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)
