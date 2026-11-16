"""Layanan otomatisasi (Phase 8, ADR 0014).

Prinsip:
- Tanpa AI dan tanpa angka buatan: laporan menampilkan angka YouTube apa adanya, berdampingan dengan nilai
  sebelumnya (tanpa selisih, persentase, atau prediksi). Pemberitahuan berisi fakta (video/judul baru).
- Jadwal yang terlewat (ZOI tertidur) dijalankan SEKALI saat ZOI bangun dan dilabeli "terlambat".
- Tiap jalan = tugas Task Manager (jalur "automation"): bisa dibatalkan, tercatat.
- Tidak pernah mempublikasikan apa pun.
"""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy import delete, func, select

from app.automation.schedule import Schedule
from app.db.base import utcnow
from app.db.models import Automation, AutomationRun, Notification
from app.db.session import Database
from app.tasks.manager import TaskContext, TaskKind

KINDS: dict[str, str] = {
    "laporan_channel": "Laporan channel",
    "pantau_kompetitor": "Pantau kompetitor",
    "pantau_tren": "Pantau Trending",
    "pengingat_produksi": "Pengingat produksi",
}
LATE_AFTER = timedelta(minutes=10)
MAX_AUTOMATIONS = 30
MAX_NOTIFICATIONS = 300
MAX_RUNS_PER_AUTOMATION = 60
LINKS = {"laporan_channel": "/analytics", "pantau_kompetitor": "/competitors", "pantau_tren": "/viral",
         "pengingat_produksi": "/production"}


class AutomationError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _clean_params(kind: str, params: dict[str, Any]) -> dict[str, Any]:
    if kind == "pengingat_produksi":
        text = str(params.get("text") or "").strip()
        if not text:
            raise AutomationError("Isi teks pengingat.")
        return {"text": text[:500]}
    return {}


class AutomationService:
    def __init__(self, *, db: Database, bus: Any, tasks: Any, youtube: Any, public: Any) -> None:
        self.db = db
        self.bus = bus
        self.tasks = tasks
        self.youtube = youtube
        self.public = public
        self._lock = threading.Lock()

    def _changed(self) -> None:
        self.bus.publish("automation.updated", {"unread": self.unread_count()})

    # ── CRUD ──────────────────────────────────────────────────────────────
    @staticmethod
    def _dict(row: Automation, last_run: AutomationRun | None = None) -> dict[str, Any]:
        schedule = Schedule.model_validate_json(row.schedule_json)
        return {"id": row.id, "kind": row.kind, "kind_label": KINDS.get(row.kind, row.kind), "name": row.name,
                "enabled": row.enabled, "schedule": schedule.model_dump(), "schedule_text": schedule.describe(),
                "params": json.loads(row.params_json),
                "next_due_at": row.next_due_at.isoformat() if row.next_due_at and row.enabled else None,
                "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
                "last_run": AutomationService._run_dict(last_run) if last_run else None}

    @staticmethod
    def _run_dict(run: AutomationRun) -> dict[str, Any]:
        return {"id": run.id, "automation_id": run.automation_id, "task_id": run.task_id, "trigger": run.trigger,
                "late": run.late, "status": run.status, "summary": run.summary,
                "result": json.loads(run.result_json or "{}"), "started_at": run.started_at.isoformat(),
                "finished_at": run.finished_at.isoformat() if run.finished_at else None}

    def list(self) -> list[dict[str, Any]]:
        with self.db.session() as s:
            rows = s.scalars(select(Automation).order_by(Automation.created_at)).all()
            out = []
            for row in rows:
                last = s.scalars(select(AutomationRun).where(AutomationRun.automation_id == row.id)
                                 .order_by(AutomationRun.started_at.desc()).limit(1)).first()
                out.append(self._dict(row, last))
            return out

    def create(self, kind: str, name: str, schedule: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        if kind not in KINDS:
            raise AutomationError("Jenis otomatisasi tidak dikenal.")
        try:
            sched = Schedule.model_validate(schedule)
        except ValidationError as exc:
            raise AutomationError("Jadwal tidak valid.") from exc
        clean = _clean_params(kind, params)
        with self.db.session() as s:
            if (s.scalar(select(func.count()).select_from(Automation)) or 0) >= MAX_AUTOMATIONS:
                raise AutomationError(f"Maksimal {MAX_AUTOMATIONS} otomatisasi.", 409)
            row = Automation(id=str(uuid.uuid4()), kind=kind, name=(name.strip() or KINDS[kind])[:120],
                             enabled=True, schedule_json=sched.model_dump_json(), params_json=json.dumps(clean),
                             next_due_at=sched.next_after(utcnow()))
            s.add(row)
            s.flush()
            result = self._dict(row)
        self._changed()
        return result

    def update(self, automation_id: str, *, enabled: bool | None = None, name: str | None = None,
               schedule: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.db.session() as s:
            row = s.get(Automation, automation_id)
            if row is None:
                raise AutomationError("Otomatisasi tidak ditemukan.", 404)
            if name is not None:
                row.name = name.strip()[:120] or KINDS[row.kind]
            if params is not None:
                row.params_json = json.dumps(_clean_params(row.kind, params))
            if schedule is not None:
                try:
                    row.schedule_json = Schedule.model_validate(schedule).model_dump_json()
                except ValidationError as exc:
                    raise AutomationError("Jadwal tidak valid.") from exc
            if enabled is not None:
                row.enabled = enabled
            if schedule is not None or enabled:
                row.next_due_at = Schedule.model_validate_json(row.schedule_json).next_after(utcnow())
            result = self._dict(row)
        self._changed()
        return result

    def delete(self, automation_id: str) -> None:
        with self.db.session() as s:
            row = s.get(Automation, automation_id)
            if row is None:
                raise AutomationError("Otomatisasi tidak ditemukan.", 404)
            s.execute(delete(AutomationRun).where(AutomationRun.automation_id == automation_id))
            s.delete(row)
        self._changed()

    def runs(self, automation_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        with self.db.session() as s:
            query = select(AutomationRun).order_by(AutomationRun.started_at.desc()).limit(limit)
            if automation_id:
                query = query.where(AutomationRun.automation_id == automation_id)
            return [self._run_dict(r) for r in s.scalars(query).all()]

    # ── notifikasi ────────────────────────────────────────────────────────
    def notify(self, kind: str, title: str, body: str, link: str | None = None) -> None:
        with self.db.session() as s:
            s.add(Notification(id=str(uuid.uuid4()), kind=kind, title=title[:200], body=body[:4000], link=link))
            s.flush()
            ids = s.scalars(select(Notification.id).order_by(Notification.created_at.desc())
                            .offset(MAX_NOTIFICATIONS)).all()
            if ids:
                s.execute(delete(Notification).where(Notification.id.in_(ids)))
        self._changed()

    def notifications(self, limit: int = 50) -> dict[str, Any]:
        with self.db.session() as s:
            rows = s.scalars(select(Notification).order_by(Notification.created_at.desc()).limit(limit)).all()
            items = [{"id": r.id, "kind": r.kind, "title": r.title, "body": r.body, "link": r.link,
                      "created_at": r.created_at.isoformat(), "read": r.read_at is not None} for r in rows]
        return {"items": items, "unread": self.unread_count()}

    def unread_count(self) -> int:
        with self.db.session() as s:
            return int(s.scalar(select(func.count()).select_from(Notification)
                                .where(Notification.read_at.is_(None))) or 0)

    def mark_read(self, notification_id: str | None = None) -> None:
        with self.db.session() as s:
            query = select(Notification).where(Notification.read_at.is_(None))
            if notification_id:
                query = query.where(Notification.id == notification_id)
            for row in s.scalars(query).all():
                row.read_at = utcnow()
        self._changed()

    # ── menjalankan ───────────────────────────────────────────────────────
    def _active(self, s: Any, automation_id: str) -> bool:
        return s.scalars(select(AutomationRun.id).where(AutomationRun.automation_id == automation_id,
                                                        AutomationRun.status == "RUNNING")).first() is not None

    def run_now(self, automation_id: str) -> dict[str, Any]:
        with self._lock, self.db.session() as s:
            row = s.get(Automation, automation_id)
            if row is None:
                raise AutomationError("Otomatisasi tidak ditemukan.", 404)
            if self._active(s, automation_id):
                raise AutomationError("Otomatisasi ini sedang berjalan.", 409)
            return self._start(s, row, trigger="manual", late=False)

    def _start(self, s: Any, row: Automation, *, trigger: str, late: bool) -> dict[str, Any]:
        run = AutomationRun(id=str(uuid.uuid4()), automation_id=row.id, trigger=trigger, late=late,
                            status="RUNNING", summary="", result_json="{}")
        s.add(run)
        row.last_run_at = utcnow()
        s.commit()  # baris jalan harus sudah tersimpan sebelum tugas (thread lain) mulai
        task = self.tasks.submit("automation_run", {"automation_id": row.id, "run_id": run.id},
                                 name=f"Otomatisasi: {row.name}")
        run.task_id = task["id"]
        return {"run_id": run.id, "task": task}

    def check_due(self, trigger: str = "jadwal") -> list[dict[str, Any]]:
        """Jalankan otomatisasi yang jatuh tempo. Yang terlewat lama hanya dijalankan SEKALI (susulan)."""
        started: list[dict[str, Any]] = []
        now = utcnow()
        with self._lock, self.db.session() as s:
            rows = s.scalars(select(Automation).where(Automation.enabled.is_(True),
                                                      Automation.next_due_at.is_not(None),
                                                      Automation.next_due_at <= now)).all()
            for row in rows:
                late = now - row.next_due_at > LATE_AFTER
                row.next_due_at = Schedule.model_validate_json(row.schedule_json).next_after(now)
                if self._active(s, row.id):
                    continue
                kind = "susulan" if late and trigger == "jadwal" else trigger
                started.append(self._start(s, row, trigger=kind, late=late))
        if started:
            self._changed()
        return started

    def recover(self) -> None:
        """Jalan yang tertinggal berstatus RUNNING setelah server dimulai ulang → ditandai terputus, jujur."""
        with self.db.session() as s:
            for run in s.scalars(select(AutomationRun).where(AutomationRun.status == "RUNNING")).all():
                run.status = "FAILED"
                run.summary = "Terputus: server dimulai ulang sebelum selesai. Tidak diulang otomatis."
                run.finished_at = utcnow()

    def _finish(self, run_id: str, status: str, summary: str, result: dict[str, Any]) -> None:
        with self.db.session() as s:
            run = s.get(AutomationRun, run_id)
            if run is None:
                return
            run.status, run.summary, run.finished_at = status, summary[:4000], utcnow()
            run.result_json = json.dumps(result, ensure_ascii=False, default=str)
            old = s.scalars(select(AutomationRun.id).where(AutomationRun.automation_id == run.automation_id)
                            .order_by(AutomationRun.started_at.desc()).offset(MAX_RUNS_PER_AUTOMATION)).all()
            if old:
                s.execute(delete(AutomationRun).where(AutomationRun.id.in_(old)))
        self._changed()

    # ── isi tiap jenis ────────────────────────────────────────────────────
    def _channel_report(self, run_async: Callable[..., Any]) -> tuple[str, str, dict[str, Any]]:
        if not self.youtube.account():
            raise AutomationError("Akun YouTube belum terhubung. Hubungkan di Settings › YouTube.")
        before = (self.youtube.data().get("channel") or {}).get("payload") or {}
        run_async(self.youtube.refresh_all(), timeout=120)
        data = self.youtube.data()
        now = (data.get("channel") or {}).get("payload") or {}
        lines = []
        for key, label in (("subscriber_count", "Subscriber"), ("view_count", "Total tayangan"),
                           ("video_count", "Jumlah video")):
            value = now.get(key)
            prev = before.get(key)
            if key == "subscriber_count" and now.get("hidden_subscribers"):
                lines.append(f"{label}: disembunyikan oleh pemilik channel")
                continue
            text = f"{label}: {value if value is not None else '—'}"
            if prev is not None and prev != value:
                text += f" (sebelumnya {prev})"
            lines.append(text)
        analytics = ((data.get("analytics") or {}).get("payload") or {}).get("last_28_days") or {}
        rows = analytics.get("rows") or []
        if rows:
            row = rows[0]
            lines.append(f"28 hari terakhir ({analytics.get('start')} s.d. {analytics.get('end')}): "
                         f"tayangan {row.get('views', '—')}, menit tonton {row.get('estimatedMinutesWatched', '—')}")
        ypp = data.get("ypp") or {}
        if ypp.get("tiers"):
            tier = ypp["tiers"][0]
            lines.append(f"Syarat YPP ({tier['name']}): " + "; ".join(tier["requirements"]) +
                         f" — dicek {ypp.get('checked_at')}, sumber resmi YouTube.")
        lines.append("Sumber: YouTube Data API & Analytics API. Angka apa adanya, tanpa perkiraan.")
        title = f"Laporan channel: {now.get('title') or 'channel-mu'}"
        return title, "\n".join(lines), {"channel": now}

    def _competitor_watch(self, run_async: Callable[..., Any]) -> tuple[str, str, dict[str, Any]]:
        items = self.public.competitors()["items"]
        if not items:
            raise AutomationError("Daftar pantauan kompetitor kosong. Tambahkan di Competitor Intelligence.")
        news: list[str] = []
        failed: list[str] = []
        for item in items:
            cid = item["channel_id"]
            old = ((item.get("data") or {}).get("payload") or {}).get("videos")
            old_ids = {v["id"] for v in old or []}
            try:
                run_async(self.public.refresh_competitor(cid), timeout=60)
            except Exception as exc:  # noqa: BLE001 — dilaporkan per channel
                failed.append(f"{cid}: {getattr(exc, 'message', str(exc))}")
                continue
            fresh = (self.public.get(f"competitor:{cid}") or {}).get("payload") or {}
            name = (fresh.get("channel") or {}).get("title") or cid
            if old is not None:
                for video in fresh.get("videos") or []:
                    if video["id"] not in old_ids:
                        news.append(f"{name}: {video['title']}")
        lines = [f"{len(items)} channel diperiksa."]
        lines += [f"Video baru — {n}" for n in news] or ["Tidak ada video baru sejak pemeriksaan sebelumnya."]
        lines += [f"Gagal — {f}" for f in failed]
        title = f"{len(news)} video baru dari kompetitor" if news else "Pantau kompetitor: tidak ada video baru"
        return title, "\n".join(lines), {"new_videos": news, "failed": failed}

    def _trend_watch(self, run_async: Callable[..., Any]) -> tuple[str, str, dict[str, Any]]:
        key = "trending:ID:all"
        before = ((self.public.get(key) or {}).get("payload") or {}).get("items")
        before_ids = {v["id"] for v in before or []}
        run_async(self.public.refresh_trending(None), timeout=60)
        after = ((self.public.get(key) or {}).get("payload") or {}).get("items") or []
        new = [v["title"] for v in after if v["id"] not in before_ids] if before is not None else []
        lines = [f"Trending YouTube Indonesia: {len(after)} video (urutan dari YouTube)."]
        if before is None:
            lines.append("Pemeriksaan pertama — belum ada pembanding.")
        else:
            lines += [f"Baru masuk: {t}" for t in new[:15]] or ["Tidak ada judul baru sejak pemeriksaan sebelumnya."]
        title = f"{len(new)} judul baru di Trending" if new else "Pantau Trending: tidak ada judul baru"
        return title, "\n".join(lines), {"new_titles": new[:50], "count": len(after)}

    def task_kind(self, run_async: Callable[..., Any]) -> TaskKind:
        def run(ctx: TaskContext) -> dict[str, Any]:
            automation_id, run_id = ctx.params["automation_id"], ctx.params["run_id"]
            name = "otomatisasi"
            try:
                with self.db.session() as s:
                    row = s.get(Automation, automation_id)
                    if row is None:
                        raise AutomationError("Otomatisasi sudah dihapus.")
                    kind, name, params = row.kind, row.name, json.loads(row.params_json)
                ctx.progress(10, f"Menjalankan {KINDS.get(kind, kind).lower()}…")
                if kind == "laporan_channel":
                    title, body, result = self._channel_report(run_async)
                elif kind == "pantau_kompetitor":
                    title, body, result = self._competitor_watch(run_async)
                elif kind == "pantau_tren":
                    title, body, result = self._trend_watch(run_async)
                else:
                    title, body, result = f"Pengingat: {name}", params.get("text", ""), {}
                ctx.check_cancelled()
            except Exception as exc:
                message = getattr(exc, "message", None) or str(exc) or type(exc).__name__
                cancelled = ctx.cancel_event.is_set()
                self._finish(run_id, "CANCELLED" if cancelled else "FAILED", message, {})
                if not cancelled:
                    self.notify("otomatisasi_gagal", f"Otomatisasi gagal: {name}", message, "/automation")
                raise
            self._finish(run_id, "COMPLETED", body, result)
            self.notify(kind, title, body, LINKS.get(kind))
            return {"title": title, "summary": body}

        return TaskKind(kind="automation_run", name="Otomatisasi", func=run, lane="automation")
