from __future__ import annotations

from fastapi import APIRouter

from app.api import (
    agent_api,
    ai,
    ai_cloud,
    auth,
    backup,
    chat,
    content,
    health,
    memory,
    production,
    system,
    tasks,
    voice,
    ws,
    youtube,
    youtube_public,
)

api_router = APIRouter(prefix="/api")
for module in (health, auth, backup, system, tasks, chat, ai, voice, memory, agent_api, youtube,
               youtube_public, content, ai_cloud, production):
    api_router.include_router(module.router)

ws_router = ws.router
