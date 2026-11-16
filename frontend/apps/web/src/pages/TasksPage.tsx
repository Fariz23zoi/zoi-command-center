import { api, ApiError } from "@zoi/api-client";
import { useState } from "react";

import { formatTime } from "../lib/format";
import { useApp } from "../stores/appStore";

const STATUS_LABEL: Record<string, string> = {
  QUEUED: "Menunggu", RUNNING: "Berjalan", COMPLETED: "Selesai", FAILED: "Gagal", CANCELLED: "Dibatalkan",
};

export function TasksPage() {
  const tasks = useApp((s) => s.tasks);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try { await action(); } catch (err) { setError(err instanceof ApiError ? err.message : "Permintaan gagal."); }
  }

  return (
    <section className="page">
      <h1>Task Manager</h1>
      <div className="row">
        <button type="button" className="primary" onClick={() => run(api.runSystemCheck)}>Jalankan pemeriksaan sistem</button>
      </div>
      {error && <p className="notice bad" role="alert">{error}</p>}
      {tasks.length === 0 && <p className="muted">Belum ada tugas.</p>}
      <ul className="task-list">
        {tasks.map((t) => (
          <li key={t.id} className={`task task-${t.status.toLowerCase()}`} data-testid="task-item">
            <div className="task-head">
              <strong>{t.name}</strong>
              <span className="badge" data-testid="task-status">{STATUS_LABEL[t.status] ?? t.status}</span>
            </div>
            <progress max={100} value={t.progress} aria-label={`Progress ${t.name}`} />
            <p className="muted">{t.message} · ID {t.id.slice(0, 8)} · {formatTime(t.created_at)}</p>
            {t.error && <p className="msg-error">{t.error}</p>}
            {(t.status === "QUEUED" || t.status === "RUNNING") && (
              <button type="button" onClick={() => run(() => api.cancelTask(t.id))}>Batalkan</button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
