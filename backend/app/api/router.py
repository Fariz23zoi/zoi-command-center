from __future__ import annotations

from fastapi import APIRouter

from app.api import chat, health, system, tasks, ws

api_router = APIRouter(prefix="/api")
for module in (health, system, tasks, chat):
    api_router.include_router(module.router)

ws_router = ws.router
