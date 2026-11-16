from __future__ import annotations

from fastapi import APIRouter

from app.api import agent_api, ai, chat, health, memory, system, tasks, voice, ws, youtube

api_router = APIRouter(prefix="/api")
for module in (health, system, tasks, chat, ai, voice, memory, agent_api, youtube):
    api_router.include_router(module.router)

ws_router = ws.router
