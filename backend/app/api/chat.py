from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.chat.service import MAX_MESSAGE_CHARS
from app.context import AppContext, get_ctx

router = APIRouter()


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    conversation_id: str | None = Field(default=None, max_length=36)


@router.post("/chat", status_code=202)
async def send_message(body: ChatRequest, ctx: AppContext = Depends(get_ctx)) -> dict:
    return await ctx.chat.send(body.message, body.conversation_id)


@router.get("/conversations")
def conversations(ctx: AppContext = Depends(get_ctx)) -> dict:
    return {"conversations": ctx.chat.list_conversations()}


@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: str, ctx: AppContext = Depends(get_ctx)) -> dict:
    return {"messages": ctx.chat.messages(conversation_id)}
