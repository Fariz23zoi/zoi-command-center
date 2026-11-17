from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.chat.attachments import MAX_FILES, MAX_TEXT_PER_FILE, extract
from app.chat.service import MAX_MESSAGE_CHARS
from app.context import AppContext, get_ctx

router = APIRouter()


class Attachment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=MAX_TEXT_PER_FILE)
    truncated: bool = False
    chars: int | None = None


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    conversation_id: str | None = Field(default=None, max_length=36)
    attachments: list[Attachment] = Field(default_factory=list, max_length=MAX_FILES)


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    data_base64: str = Field(min_length=1, max_length=14 * 1024 * 1024)


@router.post("/chat", status_code=202)
async def send_message(body: ChatRequest, ctx: AppContext = Depends(get_ctx)) -> dict:
    return await ctx.chat.send(body.message, body.conversation_id, [a.model_dump() for a in body.attachments])


@router.post("/attachments/extract")
def extract_attachment(body: ExtractRequest) -> dict:
    """Ambil teks dari file lampiran (diproses di laptop ini; file tidak disimpan)."""
    return extract(body.name, body.data_base64)


@router.post("/chat/{message_id}/stop")
def stop_message(message_id: str, ctx: AppContext = Depends(get_ctx)) -> dict:
    """Menghentikan jawaban yang sedang ditulis. stopped=false bila jawaban sudah selesai."""
    return {"stopped": ctx.chat.stop(message_id)}


@router.get("/conversations")
def conversations(ctx: AppContext = Depends(get_ctx)) -> dict:
    return {"conversations": ctx.chat.list_conversations()}


@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: str, ctx: AppContext = Depends(get_ctx)) -> dict:
    return {"messages": ctx.chat.messages(conversation_id)}


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, ctx: AppContext = Depends(get_ctx)) -> None:
    ctx.chat.delete_conversation(conversation_id)
