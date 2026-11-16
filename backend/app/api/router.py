from __future__ import annotations

from fastapi import APIRouter

from app.api import (
    agent_api,
    ai,
    ai_cloud,
    auth,
    chat,
    content,
    health,
    memory,
    system,
    tasks,
    voice,
    ws,
    youtube,
    youtube_public,
)

api_router = APIRouter(prefix="/api")
for module in (health, auth, system, tasks, chat, ai, voice, memory, agent_api, youtube, youtube_public,
               content, ai_cloud):
    api_router.include_router(module.router)

ws_router = ws.router
