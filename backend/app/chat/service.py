"""Chat: pesan → provider (Mock/Ollama) → jawaban bertahap lewat WebSocket → disimpan.

Setiap pesan menyimpan nama provider dan tanda is_mock, sehingga data mock bisa dipisahkan saat migrasi.
Phase 3: riwayat dipotong sesuai jendela konteks model, proses berpikir disimpan terpisah, jawaban bisa dihentikan.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy import delete, select, update

from app.core.agent_state import AgentState, AgentStateTracker
from app.core.errors import NotFound, ZoiError
from app.core.events import EventBus
from app.db.base import utcnow
from app.db.models import AgentRun, Conversation, Message
from app.db.session import Database
from app.logging_setup import get_logger
from app.memory.service import MemoryService
from app.providers.base import ChatMessage, LLMProvider

log = get_logger("chat")

MAX_MESSAGE_CHARS = 4000
HISTORY_LIMIT = 40
# Perkiraan kasar token dari jumlah karakter (Bahasa Indonesia ±3,5 karakter/token). Sengaja konservatif.
CHARS_PER_TOKEN = 3.5
# Bagian jendela konteks yang dipakai untuk riwayat; sisanya untuk jawaban model.
HISTORY_SHARE = 0.6
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
        self._by_message: dict[str, asyncio.Task[None]] = {}
        self.memory: MemoryService | None = None  # dipasang di main (Phase 5)

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

        message_id = result["assistant_message"]["id"]
        task = asyncio.create_task(self._stream(result["conversation_id"], message_id))
        self._running.add(task)
        self._by_message[message_id] = task

        def _done(t: asyncio.Task[None]) -> None:
            self._running.discard(t)
            self._by_message.pop(message_id, None)

        task.add_done_callback(_done)
        return result

    def add_message(self, *, conversation_id: str | None, role: str, content: str,
                    agent_run_id: str | None = None) -> dict[str, Any]:
        """Pesan selesai (bukan streaming) untuk permintaan & ringkasan agen. Disiarkan sebagai chat.message."""
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
                conversation = Conversation(id=str(uuid.uuid4()), title=content[:60], is_mock=is_mock)
                s.add(conversation)
            conversation.updated_at = utcnow()
            message = Message(id=str(uuid.uuid4()), conversation_id=conversation.id, role=role, content=content,
                              provider=None if role == "user" else self.provider.name,
                              model=None if role == "user" else self.provider.model,
                              is_mock=is_mock, status="complete", agent_run_id=agent_run_id)
            s.add(message)
            s.flush()
            data = message_dict(message)
        self.bus.publish("chat.message", {"conversation_id": data["conversation_id"], "message": data})
        return data

    def stop(self, message_id: str) -> bool:
        """Menghentikan jawaban yang sedang berjalan. Koneksi ke penyedia AI ikut ditutup sehingga Ollama berhenti."""
        task = self._by_message.get(message_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    async def wait_idle(self) -> None:
        while self._running:
            await asyncio.gather(*list(self._running), return_exceptions=True)

    def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.db.session() as s:
            rows = s.scalars(select(Conversation).order_by(Conversation.updated_at.desc()).limit(limit)).all()
            return [{"id": c.id, "title": c.title, "is_mock": c.is_mock, "updated_at": c.updated_at.isoformat()}
                    for c in rows]

    def delete_conversation(self, conversation_id: str) -> None:
        """Menghapus percakapan beserta pesannya. Riwayat agen tetap ada (tautan percakapannya dilepas)."""
        with self.db.session() as s:
            conversation = s.get(Conversation, conversation_id)
            if conversation is None:
                raise NotFound("Percakapan tidak ditemukan.")
            ids = s.scalars(select(Message.id).where(Message.conversation_id == conversation_id)).all()
            if any((t := self._by_message.get(i)) is not None and not t.done() for i in ids):
                raise ZoiError("ZOI masih menulis jawaban di percakapan ini. Hentikan dulu.", status_code=409,
                               code="busy")
            s.execute(update(AgentRun).where(AgentRun.conversation_id == conversation_id).values(conversation_id=None))
            s.execute(delete(Message).where(Message.conversation_id == conversation_id))
            s.delete(conversation)
        self.bus.publish("chat.deleted", {"conversation_id": conversation_id})

    def messages(self, conversation_id: str) -> list[dict[str, Any]]:
        with self.db.session() as s:
            conversation = s.get(Conversation, conversation_id)
            if conversation is None:
                raise NotFound("Percakapan tidak ditemukan.")
            return [message_dict(m) for m in conversation.messages]

    def _history(self, conversation_id: str, exclude_id: str, context_tokens: int) -> list[ChatMessage]:
        with self.db.session() as s:
            rows = s.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id, Message.id != exclude_id,
                       Message.status.in_(["complete", "stopped"]), Message.content != "")
                .order_by(Message.created_at.desc())
                .limit(HISTORY_LIMIT)
            ).all()
            newest_first = [ChatMessage(role=m.role, content=m.content) for m in rows]  # type: ignore[arg-type]
        latest_user = next((m.content for m in newest_first if m.role == "user"), "")
        block = self.memory.prompt_block(latest_user) if self.memory and latest_user else None
        if not block:
            return trim_history(newest_first, context_tokens)
        # Memori relevan disisipkan sebagai DATA tepat setelah system prompt; anggaran riwayat dikurangi.
        trimmed = trim_history(newest_first, max(512, context_tokens - estimate_tokens(block)))
        return [trimmed[0], ChatMessage(role="system", content=block), *trimmed[1:]]

    async def _stream(self, conversation_id: str, message_id: str) -> None:
        self.agent.set(AgentState.THINKING, "Menyusun jawaban")
        parts: list[str] = []
        thinking: list[str] = []
        error: str | None = None
        stopped = False
        speaking = False
        served: tuple[str | None, str | None, str | None] | None = None
        try:
            history = self._history(conversation_id, message_id, await self.provider.context_tokens())
            async for chunk in self.provider.chat(history):
                if chunk.type == "thinking":
                    thinking.append(chunk.text)
                    self.bus.publish("chat.thinking", {"conversation_id": conversation_id, "message_id": message_id,
                                                       "text": chunk.text})
                elif chunk.type == "text":
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
                    if chunk.served_by:
                        served = (chunk.served_by, chunk.served_model, chunk.note)
                    break
        except asyncio.CancelledError:
            stopped = True
        except Exception as exc:  # noqa: BLE001 — dilaporkan ke pengguna, tidak disembunyikan
            log.exception("chat_stream_failed", message_id=message_id)
            error = f"Kesalahan internal: {type(exc).__name__}"

        with self.db.session() as s:
            message = s.get(Message, message_id)
            assert message is not None
            message.content = "".join(parts)
            message.thinking = "".join(thinking) or None
            message.status = "stopped" if stopped else "error" if error else "complete"
            message.error = None if stopped else error
            if served:  # yang menjawab bukan penyedia utama → label pesan mengikuti yang sebenarnya
                message.provider, message.model, message.note = served[0], served[1], (served[2] or "")[:600]
            final = message_dict(message)
        self.bus.publish("chat.done", {"conversation_id": conversation_id, "message": final})
        if stopped:
            self.agent.set(AgentState.IDLE, "Jawaban dihentikan")
        elif error:
            self.agent.set(AgentState.FAILED, error[:120])
        else:
            self.agent.set(AgentState.COMPLETED, "Jawaban selesai")


def message_dict(m: Message) -> dict[str, Any]:
    return {
        "id": m.id, "conversation_id": m.conversation_id, "role": m.role, "content": m.content,
        "provider": m.provider, "model": m.model, "is_mock": m.is_mock, "status": m.status, "error": m.error,
        "note": m.note,
        "thinking": m.thinking, "agent_run_id": m.agent_run_id,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def estimate_tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN) + 4  # +4: kerangka peran per pesan


def trim_history(newest_first: list[ChatMessage], context_tokens: int) -> list[ChatMessage]:
    """System prompt + pesan terbaru yang muat di anggaran konteks. Pesan terbaru (pertanyaan saat ini) selalu ikut,
    dipotong bila sendirian sudah melebihi anggaran."""
    system = ChatMessage(role="system", content=SYSTEM_PROMPT)
    budget = int(context_tokens * HISTORY_SHARE) - estimate_tokens(SYSTEM_PROMPT)
    kept: list[ChatMessage] = []
    for message in newest_first:
        cost = estimate_tokens(message.content)
        if cost > budget:
            if not kept:
                limit = max(0, int((budget - 4) * CHARS_PER_TOKEN))
                kept.append(ChatMessage(role=message.role, content=message.content[-limit:] if limit else ""))
            break
        kept.append(message)
        budget -= cost
    return [system, *reversed(kept)]
