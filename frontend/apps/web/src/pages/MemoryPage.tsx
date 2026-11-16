import {
  type AgentToolInfo, api, ApiError, type ApprovalInfo, type MemoryInfo, type MemoryKind,
} from "@zoi/api-client";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { formatTime } from "../lib/format";
import { useApp } from "../stores/appStore";

const KINDS: { value: MemoryKind; label: string }[] = [
  { value: "fakta", label: "Fakta" }, { value: "preferensi", label: "Preferensi" }, { value: "proyek", label: "Proyek" },
];
const CONFIRM = "HAPUS SEMUA";
const APPROVAL_LABEL: Record<ApprovalInfo["status"], string> = {
  pending: "menunggu", approved: "disetujui", rejected: "ditolak", expired: "kedaluwarsa", auto: "otomatis (diizinkan)",
};

function errorText(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

/** Memori jangka panjang ZOI: semua bisa dilihat, dicari, diubah, dan dihapus. Ditambah izin tool & log izin agen. */
export function MemoryPage() {
  const revision = useApp((s) => s.memoryRevision);
  const [items, setItems] = useState<MemoryInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState({ content: "", kind: "fakta" as MemoryKind });
  const [editing, setEditing] = useState<{ id: string; content: string; kind: MemoryKind } | null>(null);
  const [confirm, setConfirm] = useState("");
  const [notice, setNotice] = useState<{ kind: "ok" | "bad"; text: string } | null>(null);

  const load = useCallback(() => {
    api.memories.list(query.trim() || undefined)
      .then((r) => { setItems(r.items); setTotal(r.total); })
      .catch((err) => setNotice({ kind: "bad", text: errorText(err, "Memori tidak dapat dimuat.") }));
  }, [query]);

  useEffect(() => { load(); }, [load, revision]);

  async function run(action: () => Promise<unknown>, ok: string) {
    setNotice(null);
    try {
      await action();
      setNotice({ kind: "ok", text: ok });
      load();
    } catch (err) {
      setNotice({ kind: "bad", text: errorText(err, "Permintaan gagal.") });
    }
  }

  async function add(event: FormEvent) {
    event.preventDefault();
    if (!draft.content.trim()) return;
    await run(() => api.memories.create(draft.content, draft.kind), "Memori ditambahkan.");
    setDraft({ content: "", kind: draft.kind });
  }

  return (
    <section className="page" data-testid="memory-page">
      <h1>Memory</h1>
      <p className="muted">
        Catatan jangka panjang yang dipakai ZOI saat menjawab dan merencanakan. Semuanya tersimpan di komputer ini,
        ikut ekspor data, dan bisa kamu ubah atau hapus kapan saja. Agen tidak pernah menyimpan memori tanpa izinmu.
      </p>
      {notice && <p className={`notice ${notice.kind}`} role="status" data-testid="memory-notice">{notice.text}</p>}

      <h2>Tambah memori</h2>
      <form className="form" onSubmit={add}>
        <label htmlFor="memory-content">Isi</label>
        <textarea id="memory-content" value={draft.content} maxLength={1000} rows={2}
          onChange={(e) => setDraft({ ...draft, content: e.target.value })} />
        <label htmlFor="memory-kind">Jenis</label>
        <select id="memory-kind" value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value as MemoryKind })}>
          {KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
        </select>
        <button type="submit" className="primary" disabled={!draft.content.trim()}>Simpan memori</button>
      </form>

      <h2>Memori tersimpan ({total})</h2>
      <label htmlFor="memory-search" className="sr-only">Cari memori</label>
      <input id="memory-search" type="search" placeholder="Cari kata…" value={query} onChange={(e) => setQuery(e.target.value)} />
      {items.length === 0 ? (
        <p className="muted">{query.trim() ? "Tidak ada memori yang cocok." : "Belum ada memori."}</p>
      ) : (
        <ul className="model-list" data-testid="memory-list">
          {items.map((m) => (
            <li key={m.id} className="model-item" data-testid="memory-item">
              {editing?.id === m.id ? (
                <form className="form" onSubmit={(e) => {
                  e.preventDefault();
                  void run(() => api.memories.update(m.id, editing.content, editing.kind), "Memori diubah.")
                    .then(() => setEditing(null));
                }}>
                  <label htmlFor={`edit-${m.id}`} className="sr-only">Ubah isi</label>
                  <textarea id={`edit-${m.id}`} value={editing.content} maxLength={1000} rows={2}
                    onChange={(e) => setEditing({ ...editing, content: e.target.value })} />
                  <label htmlFor={`edit-kind-${m.id}`} className="sr-only">Jenis</label>
                  <select id={`edit-kind-${m.id}`} value={editing.kind}
                    onChange={(e) => setEditing({ ...editing, kind: e.target.value as MemoryKind })}>
                    {KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
                  </select>
                  <div className="row">
                    <button type="submit" className="primary">Simpan perubahan</button>
                    <button type="button" onClick={() => setEditing(null)}>Batal</button>
                  </div>
                </form>
              ) : (
                <>
                  <div className="model-head">
                    <span className="badge">{m.kind}</span>
                    <span className="badge">{m.source === "agen" ? "disimpan agen" : "dari kamu"}</span>
                    {m.is_mock && <span className="badge mock">MOCK</span>}
                    <span className="muted">{formatTime(m.updated_at)}</span>
                  </div>
                  <p className="model-fit">{m.content}</p>
                  <div className="row">
                    <button type="button" onClick={() => setEditing({ id: m.id, content: m.content, kind: m.kind })}>Ubah</button>
                    <button type="button" onClick={() => run(() => api.memories.remove(m.id), "Memori dihapus.")}
                      aria-label={`Hapus memori: ${m.content.slice(0, 40)}`}>Hapus</button>
                  </div>
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      {total > 0 && (
        <div className="notice bad">
          <label htmlFor="memory-confirm">Hapus semua memori — ketik <strong>{CONFIRM}</strong> untuk mengonfirmasi</label>
          <div className="row">
            <input id="memory-confirm" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="off" />
            <button type="button" disabled={confirm !== CONFIRM}
              onClick={() => run(() => api.memories.removeAll(confirm), "Semua memori dihapus.").then(() => setConfirm(""))}>
              Hapus semua memori
            </button>
          </div>
        </div>
      )}

      <AgentPermissions />
      <ApprovalLog revision={revision} />
    </section>
  );
}

function AgentPermissions() {
  const [tools, setTools] = useState<AgentToolInfo[]>([]);
  const [detail, setDetail] = useState<string | null>(null);
  useEffect(() => {
    api.agent.status().then((s) => { setTools(s.tools); setDetail(s.detail); }).catch(() => setDetail(null));
  }, []);
  async function toggle(tool: AgentToolInfo) {
    const next = tool.mode === "auto" ? "ask" : "auto";
    setTools((await api.agent.setPermission(tool.name, next)).tools);
  }
  return (
    <>
      <h2>Izin tool agen</h2>
      {detail && <p className="muted" data-testid="agent-availability">{detail}</p>}
      <p className="muted">Tool baca berjalan setelah rencana disetujui. Tool yang mengubah data meminta izin setiap langkah,
        kecuali kamu mengizinkannya otomatis di sini. ZOI tidak punya tool untuk mempublikasikan apa pun.</p>
      <ul className="model-list" data-testid="agent-tools">
        {tools.map((t) => (
          <li key={t.name} className="model-item">
            <div className="model-head"><code>{t.name}</code><span className="badge">{t.permission}</span></div>
            <p className="model-fit">{t.description}</p>
            {t.permission === "write_local" && (
              <label className="check">
                <input type="checkbox" checked={t.mode === "auto"} onChange={() => void toggle(t)} />
                Izinkan otomatis tanpa bertanya
              </label>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}

function ApprovalLog({ revision }: { revision: number }) {
  const [log, setLog] = useState<ApprovalInfo[]>([]);
  useEffect(() => { api.agent.approvals().then((r) => setLog(r.approvals)).catch(() => setLog([])); }, [revision]);
  return (
    <>
      <h2>Log izin</h2>
      {log.length === 0 ? <p className="muted">Belum ada keputusan izin.</p> : (
        <ul className="model-list" data-testid="approval-log">
          {log.map((a) => (
            <li key={a.id} className="model-item">
              <div className="model-head">
                <code>{a.tool}</code>
                <span className="badge">{APPROVAL_LABEL[a.status]}</span>
                {a.is_mock && <span className="badge mock">MOCK</span>}
                <span className="muted">{formatTime(a.decided_at ?? a.created_at)}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
