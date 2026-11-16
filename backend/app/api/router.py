from __future__ import annotations

from fastapi import APIRouter

from app.api import ai, chat, health, system, tasks, voice, ws

api_router = APIRouter(prefix="/api")
for module in (health, system, tasks, chat, ai, voice):
    api_router.include_router(module.router)

ws_router = ws.router
