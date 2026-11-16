from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.context import AppContext
from app.security.remote import remote_denied

router = APIRouter()


@router.websocket("/ws")
async def events(websocket: WebSocket) -> None:
    ctx: AppContext = websocket.app.state.zoi
    origin = websocket.headers.get("origin")
    allowed = set(ctx.runtime.cors_origins) | set(ctx.runtime.self_origins)
    if origin is not None and origin not in allowed:
        await websocket.close(code=1008, reason="Origin tidak diizinkan")
        return
    if remote_denied(ctx.runtime, websocket.headers):
        await websocket.close(code=1008, reason="Akses Tailscale ditolak")
        return
    if not ctx.auth.check(websocket.cookies.get("zoi_session")):
        await websocket.close(code=1008, reason="Belum login")
        return
    await websocket.accept()
    queue = ctx.bus.subscribe()
    try:
        await websocket.send_json({"type": "hello", "payload": {
            "mode": ctx.runtime.mode.value, "agent": ctx.agent.snapshot(), "is_mock": ctx.provider.is_mock}})
        receiver = asyncio.create_task(_drain(websocket))
        while not receiver.done():
            getter = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait({getter, receiver}, return_when=asyncio.FIRST_COMPLETED)
            if getter in done:
                await websocket.send_json(getter.result())
            else:
                getter.cancel()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        ctx.bus.unsubscribe(queue)
        with contextlib.suppress(Exception):
            await websocket.close()


async def _drain(websocket: WebSocket) -> None:
    """Klien tidak perlu mengirim apa pun; loop ini hanya mendeteksi koneksi yang ditutup."""
    with contextlib.suppress(WebSocketDisconnect):
        while True:
            await websocket.receive_text()
