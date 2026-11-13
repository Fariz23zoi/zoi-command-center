"""Status agen ZOI. Avatar HANYA menampilkan status yang benar-benar terjadi di backend."""

from __future__ import annotations

import asyncio
import threading
from enum import StrEnum

from app.core.events import EventBus


class AgentState(StrEnum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    RESEARCHING = "RESEARCHING"
    ANALYZING = "ANALYZING"
    PLANNING = "PLANNING"
    CREATING = "CREATING"
    EXECUTING = "EXECUTING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    SPEAKING = "SPEAKING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


TERMINAL_STATES = {AgentState.COMPLETED, AgentState.FAILED}
RETURN_TO_IDLE_SECONDS = 2.5


class AgentStateTracker:
    """Menyimpan status saat ini dan menyiarkannya. COMPLETED/FAILED kembali ke IDLE setelah jeda singkat."""

    def __init__(self, bus: EventBus, return_to_idle_s: float = RETURN_TO_IDLE_SECONDS) -> None:
        self._bus = bus
        self._state = AgentState.IDLE
        self._reason = "Siap"
        self._lock = threading.Lock()
        self._generation = 0
        self._return_to_idle_s = return_to_idle_s
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def state(self) -> AgentState:
        return self._state

    def snapshot(self) -> dict[str, str]:
        return {"state": self._state.value, "reason": self._reason}

    def set(self, state: AgentState, reason: str) -> None:
        with self._lock:
            self._state = state
            self._reason = reason
            self._generation += 1
            generation = self._generation
        self._bus.publish("agent.state", {"state": state.value, "reason": reason})
        if state in TERMINAL_STATES and self._loop is not None:
            self._loop.call_soon_threadsafe(self._schedule_idle, generation)

    def _schedule_idle(self, generation: int) -> None:
        assert self._loop is not None
        self._loop.call_later(self._return_to_idle_s, self._idle_if_unchanged, generation)

    def _idle_if_unchanged(self, generation: int) -> None:
        if generation == self._generation:
            self.set(AgentState.IDLE, "Siap")
