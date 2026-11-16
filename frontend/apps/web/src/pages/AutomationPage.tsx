import {
  api, type AutomationOverview, type AutomationSchedule, type NotificationInfo,
} from "@zoi/api-client";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { formatTime } from "../lib/format";
import { errorText } from "../lib/youtube";
import { useApp } from "../stores/appStore";

const WEEKDAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"];
const TRIGGER: Record<string, string> = { jadwal: "jadwal", susulan: "susulan (terlambat)", manual: "manual",
  bangun: "dibangunkan GitHub" };
const STATUS: Record<string, string> = { RUNNING: "Berjalan", COMPLETED: "Selesai", FAILED: "Gagal",
  CANCELLED: "Dibatalkan" };

/** Phase 8: otomatisasi terjadwal + notifikasi di dalam ZOI. Tidak ada publikasi otomatis. */
export function AutomationPage() {
  const revision = useApp((s) => s.automationRevision);
  const [data, setData] = useState<AutomationOverview | null>(null);
  const [notes, setNotes] = useState<NotificationInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [kind, setKind] = useState("laporan_channel");
  const [name, setName] = useState("");
  const [text, setText] = useState("");
  const [schedule, setSchedule] = useState<AutomationSchedule>({ frequency: "daily", hour: 7, minute: 0, weekday: 0 });

  // Beberapa pemuatan bisa tumpang tindih (event WebSocket + tombol). Hanya jawaban terbaru yang dipakai,
  // agar daftar lama yang datang terlambat tidak menimpa daftar baru.
  const latest = useRef(0);
  const load = useCallback(() => {
    const ticket = ++latest.current;
    api.automation.overview().then((d) => { if (ticket === latest.current) setData(d); },
      (e: unknown) => setError(errorText(e, "Gagal memuat otomatisasi.")));
    api.notifications.list().then((r) => {
      setNotes(r.items);
      useApp.setState({ unreadNotifications: r.unread });
    }, () => undefined);
  }, []);
  useEffect(load, [load, revision]);

  const act = (promise: Promise<unknown>) => {
    setError(null);
    promise.then(load, (e: unknown) => setError(errorText(e, "Gagal.")));
  };

  const create = (event: FormEvent) => {
    event.preventDefault();
    act(api.automation.create({ kind, name, schedule, params: kind === "pengingat_produksi" ? { text } : {} })
      .then(() => { setName(""); setText(""); }));
  };

  const setNumber = (key: keyof AutomationSchedule) => (value: string) =>
    setSchedule((s) => ({ ...s, [key]: Number(value) }));

  return (
    <section className="page" data-testid="automation-page">
      <h1>Automation</h1>
      <p className="muted">
        Jadwal dalam {data?.timezone ?? "WIB"}. Tiap jalan tercatat di Task Manager dan bisa dibatalkan. Tidak ada
        yang dipublikasikan, dan laporan berisi angka YouTube apa adanya — tanpa perkiraan.
      </p>
      {data?.online && (
        <p className={`notice ${data.wake_enabled ? "ok" : "warn"}`} data-testid="automation-wake">
          {data.wake_enabled
            ? "ZOI dibangunkan workflow GitHub Actions \"ZOI bangun\". Jadwal yang tetap terlewat dijalankan sekali saat ZOI bangun, berlabel \"terlambat\"."
            : "ZOI online tertidur saat sepi. Tanpa workflow \"ZOI bangun\" (lihat docs/DEPLOY_ONLINE.md bagian 6), jadwal baru berjalan saat ZOI dibuka, berlabel \"terlambat\"."}
        </p>
      )}
      {error && <p className="notice bad" role="alert">{error}</p>}

      <h2>Notifikasi</h2>
      {notes.length === 0 && <p className="empty">Belum ada notifikasi.</p>}
      {notes.some((n) => !n.read) && (
        <button type="button" data-testid="notifications-read-all"
                onClick={() => act(api.notifications.readAll())}>Tandai semua dibaca</button>
      )}
      <ul className="notifications" data-testid="notifications">
        {notes.slice(0, 20).map((n) => (
          <li key={n.id} className={n.read ? "read" : "unread"}>
            <details onToggle={(e) => { if ((e.target as HTMLDetailsElement).open && !n.read) act(api.notifications.read(n.id)); }}>
              <summary><strong>{n.title}</strong> <span className="muted">· {formatTime(n.created_at)}</span></summary>
              <pre className="note-body">{n.body}</pre>
              {n.link && <Link to={n.link}>Buka halaman terkait</Link>}
            </details>
          </li>
        ))}
      </ul>

      <h2>Otomatisasi</h2>
      {data && data.items.length === 0 && <p className="empty">Belum ada otomatisasi. Buat di bawah.</p>}
      {data?.items.map((a) => (
        <article key={a.id} className="panel" data-testid="automation-item">
          <h3>{a.name} <span className="muted">· {a.kind_label}</span></h3>
          <p>{a.schedule_text}{a.enabled ? ` · berikutnya ${a.next_due_at ? formatTime(a.next_due_at) : "—"}` : " · NONAKTIF"}</p>
          {a.params.text && <p className="muted">“{a.params.text}”</p>}
          {a.last_run && (
            <p className="muted" data-testid="automation-last">
              Terakhir: {STATUS[a.last_run.status]} ({TRIGGER[a.last_run.trigger]}{a.last_run.late ? ", terlambat" : ""}) ·{" "}
              {formatTime(a.last_run.started_at)}
            </p>
          )}
          <p>
            <button type="button" data-testid="automation-run" onClick={() => act(api.automation.run(a.id))}>
              Jalankan sekarang
            </button>{" "}
            <button type="button" onClick={() => act(api.automation.update(a.id, { enabled: !a.enabled }))}>
              {a.enabled ? "Nonaktifkan" : "Aktifkan"}
            </button>{" "}
            <button type="button" onClick={() => act(api.automation.remove(a.id))}>Hapus</button>
          </p>
        </article>
      ))}

      <h2>Buat otomatisasi</h2>
      <form className="form" onSubmit={create} data-testid="automation-form">
        <label>Jenis
          <select value={kind} onChange={(e) => setKind(e.target.value)} data-testid="automation-kind">
            {Object.entries(data?.kinds ?? {}).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
          </select>
        </label>
        <label>Nama (opsional)
          <input value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />
        </label>
        {kind === "pengingat_produksi" && (
          <label>Teks pengingat
            <input value={text} maxLength={500} required onChange={(e) => setText(e.target.value)}
                   data-testid="automation-text" />
          </label>
        )}
        <label>Frekuensi
          <select value={schedule.frequency}
                  onChange={(e) => setSchedule((s) => ({ ...s, frequency: e.target.value as "daily" | "weekly" }))}>
            <option value="daily">Setiap hari</option>
            <option value="weekly">Setiap minggu</option>
          </select>
        </label>
        {schedule.frequency === "weekly" && (
          <label>Hari
            <select value={schedule.weekday} onChange={(e) => setNumber("weekday")(e.target.value)}>
              {WEEKDAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
            </select>
          </label>
        )}
        <label>Jam (WIB)
          <input type="time" required value={`${String(schedule.hour).padStart(2, "0")}:${String(schedule.minute).padStart(2, "0")}`}
                 onChange={(e) => {
                   const [h, m] = e.target.value.split(":").map(Number);
                   setSchedule((s) => ({ ...s, hour: h || 0, minute: m || 0 }));
                 }} />
        </label>
        <button type="submit" data-testid="automation-create">Buat otomatisasi</button>
      </form>
    </section>
  );
}
