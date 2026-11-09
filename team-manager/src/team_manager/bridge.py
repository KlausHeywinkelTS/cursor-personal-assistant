"""Brücke tool_use_id -> Claude-Code-Agent.

Der MCP-Server erfährt nicht, welcher Subagent ihn aufruft, wohl aber die tool_use_id des Aufrufs
(`_meta["claudecode/toolUseId"]`). Der PreToolUse-Hook kennt dieselbe tool_use_id samt agent_id und
trägt sie hier ein, bevor der MCP-Aufruf eintrifft.
"""

from __future__ import annotations

import asyncio
import threading
import time

_TTL_S = 600.0


class ToolUseBridge:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, tuple[str | None, float]] = {}

    def put(self, tool_use_id: str | None, agent_id: str | None) -> None:
        """agent_id=None heißt: der Aufruf kam aus der Hauptsession."""
        if not tool_use_id:
            return
        now = time.monotonic()
        with self._lock:
            self._entries[tool_use_id] = (agent_id, now)
            if len(self._entries) > 256:
                self._entries = {k: v for k, v in self._entries.items() if now - v[1] < _TTL_S}

    def lookup(self, tool_use_id: str | None) -> tuple[bool, str | None]:
        with self._lock:
            entry = self._entries.get(tool_use_id or "")
        return (entry is not None, entry[0] if entry else None)

    async def resolve(self, tool_use_id: str | None, timeout: float) -> str | None:
        """Wartet bis zu `timeout` Sekunden auf den Hook-Eintrag. Ohne Eintrag: unbekannter Aufrufer (None)."""
        if not tool_use_id:
            return None
        deadline = time.monotonic() + timeout
        while True:
            found, agent_id = self.lookup(tool_use_id)
            if found or time.monotonic() >= deadline:
                return agent_id
            await asyncio.sleep(0.02)
