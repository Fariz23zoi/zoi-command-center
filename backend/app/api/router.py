from __future__ import annotations

from fastapi import APIRouter

from app.api import agent_api, ai, chat, content, health, memory, system, tasks, voice, ws, youtube, youtube_public

api_router = APIRouter(prefix="/api")
for module in (health, system, tasks, chat, ai, voice, memory, agent_api, youtube, youtube_public, content):
    api_router.include_router(module.router)

ws_router = ws.router
