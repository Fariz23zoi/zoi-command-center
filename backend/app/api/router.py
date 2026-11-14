from __future__ import annotations

from fastapi import APIRouter

from app.api import ai, chat, health, system, tasks, ws

api_router = APIRouter(prefix="/api")
for module in (health, system, tasks, chat, ai):
    api_router.include_router(module.router)

ws_router = ws.router
