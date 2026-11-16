"""Wadah semua layanan yang dipakai API. Dibuat sekali oleh create_app()."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import Request

from app.agent.service import AgentService
from app.ai.cloud import CloudAIService
from app.ai.local import LocalAIService
from app.chat.service import ChatService
from app.config.modes import RuntimeConfig
from app.config.settings import Settings
from app.content.service import ContentService
from app.core.agent_state import AgentStateTracker
from app.core.events import EventBus
from app.db.session import Database
from app.integrations.base import ExternalAppAdapter
from app.memory.service import MemoryService
from app.providers.base import LLMProvider
from app.security.auth import AuthService
from app.security.cost_guard import CostGuard
from app.tasks.manager import TaskManager
from app.voice.service import VoiceService
from app.youtube.public import PublicDataService
from app.youtube.service import YouTubeService


@dataclass
class AppContext:
    settings: Settings
    runtime: RuntimeConfig
    db: Database
    bus: EventBus
    agent: AgentStateTracker
    guard: CostGuard
    provider: LLMProvider
    adapters: list[ExternalAppAdapter]
    tasks: TaskManager
    chat: ChatService
    local_ai: LocalAIService
    voice: VoiceService
    memory: MemoryService
    agent_service: AgentService
    youtube: YouTubeService
    public: PublicDataService
    content: ContentService
    cloud_ai: CloudAIService
    auth: AuthService
    migration_backup: str | None = None
    started_monotonic: float = field(default_factory=time.monotonic)
    cache: dict[str, Any] = field(default_factory=dict)


def get_ctx(request: Request) -> AppContext:
    return request.app.state.zoi  # type: ignore[no-any-return]
