"""Tabel ZOI (Phase 1, 3, 5). Tidak ada path absolut mesin yang disimpan di sini."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, utcnow


class AppMeta(Base):
    """Preferensi portabel (bahasa UI, mode avatar pilihan) — BUKAN konfigurasi mesin."""

    __tablename__ = "app_meta"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)  # QUEUED RUNNING COMPLETED FAILED CANCELLED
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    events: Mapped[list[TaskEvent]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="TaskEvent.id"
    )


class TaskEvent(Base):
    __tablename__ = "task_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    status: Mapped[str] = mapped_column(String(16))
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(String(500), default="")

    task: Mapped[Task] = relationship(back_populates="events")


class SystemCheck(Base):
    __tablename__ = "system_checks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    payload_json: Mapped[str] = mapped_column(Text)


class NetworkAudit(Base):
    __tablename__ = "network_audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    host: Mapped[str] = mapped_column(String(255))
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(500), default="/")
    allowed: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(String(255), default="")


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), default="Percakapan baru")
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow, index=True)

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # Keterangan jujur tentang jawaban, mis. dijawab penyedia cadangan dan alasannya.
    note: Mapped[str | None] = mapped_column(String(600), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="complete")  # streaming complete error stopped
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    thinking: Mapped[str | None] = mapped_column(Text, nullable=True)  # proses berpikir model (Phase 3), terpisah
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # permintaan agen (Phase 5)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class ModelEvaluation(Base):
    """Hasil uji kecocokan model (Phase 3). Hanya hasil pengukuran nyata; Mock tidak pernah menulis ke sini."""

    __tablename__ = "model_evaluations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    model: Mapped[str] = mapped_column(String(120), index=True)
    machine: Mapped[str] = mapped_column(String(120))  # nama komputer tempat uji dijalankan (bukan path)
    ollama_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    prompts_version: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    summary_json: Mapped[str] = mapped_column(Text)
    results_json: Mapped[str] = mapped_column(Text)
    ratings_json: Mapped[str] = mapped_column(Text, default="{}")


class MemoryItem(Base):
    """Memori jangka panjang (Phase 5). Dicari lewat tabel FTS5 `memories_fts` (dijaga trigger di migrasi 0003)."""

    __tablename__ = "memories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), default="fakta")  # fakta | preferensi | proyek
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), default="pengguna")  # pengguna | agen
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)


class AgentRun(Base):
    """Satu permintaan agen: rencana → (persetujuan) → langkah → ringkasan."""

    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    request: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), index=True)
    plan_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    errors_json: Mapped[str] = mapped_column(Text, default="[]")
    results_json: Mapped[str] = mapped_column(Text, default="[]")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    provider: Mapped[str] = mapped_column(String(32))
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Approval(Base):
    """Keputusan izin untuk satu langkah agen yang mengubah data. Semua keputusan tercatat."""

    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    step_index: Mapped[int] = mapped_column(Integer)
    tool: Mapped[str] = mapped_column(String(64))
    args_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), index=True)  # pending approved rejected expired auto
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class YouTubeSnapshot(Base):
    """Statistik channel MILIK SENDIRI per hari (data berizin OAuth — boleh disimpan >30 hari, kebijakan III.E.4.b,
    selama izin dicek ulang tiap 30 hari). Angka persis seperti yang dikirim YouTube; tidak ada metrik buatan."""

    __tablename__ = "youtube_channel_snapshots"
    day: Mapped[str] = mapped_column(String(10), primary_key=True)  # tanggal lokal pengambilan (YYYY-MM-DD)
    channel_id: Mapped[str] = mapped_column(String(64))
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime)
    view_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subscriber_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hidden_subscribers: Mapped[bool] = mapped_column(Boolean, default=False)
    video_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


class YouTubeCache(Base):
    """Respons terakhir dari YouTube untuk channel sendiri (channel, video, laporan analitik)."""

    __tablename__ = "youtube_cache"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime)


class YouTubePublicCache(Base):
    """Data PUBLIK YouTube (channel lain, Trending, hasil pencarian) dan rangkuman tema yang dibuat darinya.
    Bukan data berizin → tidak boleh disimpan lebih dari 30 hari (kebijakan III.E.4.d); dihapus otomatis."""

    __tablename__ = "youtube_public_cache"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)


class YouTubeWatch(Base):
    """Channel yang dipantau pengguna. Hanya ID + catatan pengguna; nama & angka channel ada di cache ≤30 hari."""

    __tablename__ = "youtube_watchlist"
    channel_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    note: Mapped[str] = mapped_column(String(200), default="")
    added_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ContentItem(Base):
    """Draf buatan AI lokal: kumpulan ide atau naskah. Selalu menyimpan penyedia/model dan tanda mock."""

    __tablename__ = "content_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)  # ideas | script
    title: Mapped[str] = mapped_column(String(300))
    request_json: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[str] = mapped_column(Text)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)


class YouTubeQuota(Base):
    """Hitungan ZOI sendiri atas panggilan API per hari kuota (zona Pasifik). Bukan data dari YouTube."""

    __tablename__ = "youtube_quota"
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    units: Mapped[int] = mapped_column(Integer, default=0)
    search_calls: Mapped[int] = mapped_column(Integer, default=0)
    analytics_calls: Mapped[int] = mapped_column(Integer, default=0)


class AuthSession(Base):
    """Sesi login mode online. Hanya hash SHA-256 token yang disimpan."""

    __tablename__ = "auth_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)


class Secret(Base):
    """Rahasia terenkripsi (mode online): API key cloud, token YouTube. Nilai = token Fernet."""

    __tablename__ = "secrets"
    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class Automation(Base):
    """Otomatisasi terjadwal (Phase 8). Jadwal disimpan dalam waktu Asia/Jakarta (WIB)."""

    __tablename__ = "automations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule_json: Mapped[str] = mapped_column(Text, nullable=False)
    params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    next_due_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class AutomationRun(Base):
    __tablename__ = "automation_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    automation_id: Mapped[str] = mapped_column(ForeignKey("automations.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    trigger: Mapped[str] = mapped_column(String(16))  # jadwal | susulan | manual | bangun
    late: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="RUNNING")  # RUNNING | COMPLETED | FAILED | CANCELLED
    summary: Mapped[str] = mapped_column(Text, default="")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class Notification(Base):
    """Pemberitahuan di dalam ZOI saja (keputusan Phase 8: tanpa layanan luar)."""

    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
