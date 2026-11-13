"""Chat minimal Phase 1: pesan → provider (Mock/Ollama) → jawaban bertahap lewat WebSocket → disimpan.

Setiap pesan menyimpan nama provider dan tanda is_mock, sehingga data mock bisa dipisahkan saat migrasi.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy import select

from app.core.agent_state import AgentState, AgentStateTracker
from app.core.errors import NotFound, ZoiError
from app.core.events import EventBus
from app.db.base import utcnow
from app.db.models import Conversation, Message
from app.db.session import Database
from app.logging_setup import get_logger
from app.providers.base import ChatMessage, LLMProvider

log = get_logger("chat")

MAX_MESSAGE_CHARS = 4000
HISTORY_LIMIT = 20
SYSTEM_PROMPT = (
    "Kamu adalah ZOI, asisten YouTube yang berjalan secara lokal. Jawab dalam bahasa Indonesia yang jelas "
    "dan ringkas. Jangan pernah mengarang statistik, angka channel, atau hasil yang tidak kamu miliki; "
    "jika data belum tersedia, katakan terus terang."
)


class ChatService:
    def __init__(self, db: Database, bus: EventBus, agent: AgentStateTracker, provider: LLMProvider) -> None:
        self.db = db
        self.bus = bus
        self.agent = agent
        self.provider = provider
        self._running: set[asyncio.Task[None]] = set()

    async def send(self, text: str, conversation_id: str | None = None) -> dict[str, Any]:
        text = text.strip()
        if not text:
            raise ZoiError("Pesan tidak boleh kosong.", code="empty_message")
        if len(text) > MAX_MESSAGE_CHARS:
            raise ZoiError(f"Pesan terlalu panjang (maksimal {MAX_MESSAGE_CHARS} karakter).", code="too_long")

        is_mock = self.provider.is_mock
        with self.db.session() as s:
            if conversation_id:
                conversation = s.get(Conversation, conversation_id)
                if conversation is None:
                    raise NotFound("Percakapan tidak ditemukan.")
                if conversation.is_mock != is_mock:
                    raise ZoiError("Percakapan ini dibuat dengan penyedia AI yang berbeda. Mulai percakapan baru.",
                                   code="provider_mismatch")
            else:
                conversation = Conversation(id=str(uuid.uuid4()), title=text[:60], is_mock=is_mock)
                s.add(conversation)
            conversation.updated_at = utcnow()
            user_msg = Message(id=str(uuid.uuid4()), conversation_id=conversation.id, role="user", content=text,
                               is_mock=is_mock, status="complete")
            assistant = Message(id=str(uuid.uuid4()), conversation_id=conversation.id, role="assistant",
                                content="", provider=self.provider.name, model=self.provider.model,
                                is_mock=is_mock, status="streaming")
            s.add_all([user_msg, assistant])
            s.flush()
            result = {
                "conversation_id": conversation.id,
                "user_message": message_dict(user_msg),
                "assistant_message": message_dict(assistant),
            }

        task = asyncio.create_task(self._stream(result["conversation_id"], result["assistant_message"]["id"]))
        self._running.add(task)
        task.add_done_callback(self._running.discard)
        return result

    async def wait_idle(self) -> None:
        while self._running:
            await asyncio.gather(*list(self._running), return_exceptions=True)

    def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.db.session() as s:
            rows = s.scalars(select(Conversation).order_by(Conversation.updated_at.desc()).limit(limit)).all()
            return [{"id": c.id, "title": c.title, "is_mock": c.is_mock, "updated_at": c.updated_at.isoformat()}
                    for c in rows]

    def messages(self, conversation_id: str) -> list[dict[str, Any]]:
        with self.db.session() as s:
            conversation = s.get(Conversation, conversation_id)
            if conversation is None:
                raise NotFound("Percakapan tidak ditemukan.")
            return [message_dict(m) for m in conversation.messages]

    def _history(self, conversation_id: str, exclude_id: str) -> list[ChatMessage]:
        with self.db.session() as s:
            rows = s.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id, Message.id != exclude_id,
                       Message.status == "complete")
                .order_by(Message.created_at.desc())
                .limit(HISTORY_LIMIT)
            ).all()
            history = [ChatMessage(role=m.role, content=m.content) for m in reversed(rows)]  # type: ignore[arg-type]
        return [ChatMessage(role="system", content=SYSTEM_PROMPT), *history]

    async def _stream(self, conversation_id: str, message_id: str) -> None:
        self.agent.set(AgentState.THINKING, "Menyusun jawaban")
        parts: list[str] = []
        error: str | None = None
        speaking = False
        try:
            async for chunk in self.provider.chat(self._history(conversation_id, message_id)):
                if chunk.type == "text":
                    if not speaking:
                        self.agent.set(AgentState.SPEAKING, "Menjawab")
                        speaking = True
                    parts.append(chunk.text)
                    self.bus.publish("chat.delta", {"conversation_id": conversation_id, "message_id": message_id,
                                                    "text": chunk.text})
                elif chunk.type == "tool_call":
                    error = "Model meminta tool, tetapi eksekusi tool baru tersedia di Phase 5."
                    break
                elif chunk.type == "error":
                    error = chunk.error or "Kesalahan tidak diketahui dari penyedia AI."
                    break
                elif chunk.type == "done":
                    break
        except Exception as exc:  # noqa: BLE001 — dilaporkan ke pengguna, tidak disembunyikan
            log.exception("chat_stream_failed", message_id=message_id)
            error = f"Kesalahan internal: {type(exc).__name__}"

        with self.db.session() as s:
            message = s.get(Message, message_id)
            assert message is not None
            message.content = "".join(parts)
            message.status = "error" if error else "complete"
            message.error = error
            final = message_dict(message)
        self.bus.publish("chat.done", {"conversation_id": conversation_id, "message": final})
        if error:
            self.agent.set(AgentState.FAILED, error[:120])
        else:
            self.agent.set(AgentState.COMPLETED, "Jawaban selesai")


def message_dict(m: Message) -> dict[str, Any]:
    return {
        "id": m.id, "conversation_id": m.conversation_id, "role": m.role, "content": m.content,
        "provider": m.provider, "model": m.model, "is_mock": m.is_mock, "status": m.status, "error": m.error,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }
