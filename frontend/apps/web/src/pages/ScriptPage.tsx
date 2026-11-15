import { api, type ContentFormat, type ScriptItem } from "@zoi/api-client";
import { type FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { formatTime } from "../lib/format";
import { errorText } from "../lib/youtube";
import { useApp } from "../stores/appStore";
import { AiStamp, TaskNotice, useTaskWatch } from "./publicShared";

export function scriptToMarkdown(item: ScriptItem): string {
  const s = item.payload;
  const stamp = item.is_mock ? "MOCK — teks tiruan, bukan hasil AI." : `Draf AI lokal (${item.provider}${item.model ? ` · ${item.model}` : ""}) — periksa sebelum dipakai.`;
  const parts = s.bagian.map((b, i) =>
    `## ${i + 1}. ${b.judul}${b.durasi ? ` (${b.durasi})` : ""}\n\n**Narasi:** ${b.narasi}\n\n**Visual:** ${b.visual || "—"}`);
  return [`# ${s.judul}`, `> ${stamp}`, `**Hook:** ${s.hook}`, ...parts, s.cta ? `**CTA:** ${s.cta}` : ""]
    .filter(Boolean).join("\n\n") + "\n";
}

function download(item: ScriptItem) {
  const url = URL.createObjectURL(new Blob([scriptToMarkdown(item)], { type: "text/markdown" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `naskah-${item.id.slice(0, 8)}.md`;
  link.click();
  URL.revokeObjectURL(url);
}

/** Script & Storyboard: draf naskah per bagian (narasi + visual) oleh AI lokal. Bisa diunduh sebagai Markdown. */
export function ScriptPage() {
  const revision = useApp((s) => s.contentRevision);
  const [params] = useSearchParams();
  const [items, setItems] = useState<ScriptItem[]>([]);
  const [mock, setMock] = useState(false);
  const [draft, setDraft] = useState({
    judul: params.get("judul") ?? "", catatan: params.get("catatan") ?? "",
    format: (params.get("format") === "shorts" ? "shorts" : "panjang") as ContentFormat, durasi: "",
  });
  const [error, setError] = useState<string | null>(null);
  const { task, running, watch } = useTaskWatch();

  useEffect(() => {
    api.content.scripts().then((r) => { setItems(r.items); setMock(r.is_mock); })
      .catch((err) => setError(errorText(err, "Draf naskah tidak dapat dimuat.")));
  }, [revision]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      watch(await api.content.makeScript({ ...draft, judul: draft.judul.trim() }));
    } catch (err) {
      setError(errorText(err, "Tugas tidak dapat dimulai."));
    }
  }

  return (
    <section className="page" data-testid="script-page">
      <h1>Script &amp; Storyboard</h1>
      {mock && (
        <p className="notice warn" data-testid="content-mock-banner">
          Mode development: penyedia AI adalah MOCK. Hasil di sini teks tiruan, bukan naskah dari AI.
        </p>
      )}
      <p className="muted">
        Naskah adalah draf. AI diminta menandai bagian yang butuh riset dengan “[perlu riset: …]” — periksa semua fakta
        sebelum merekam. Subtitle dan timing presisi dikerjakan saat produksi (Phase 7).
      </p>
      {error && <p className="notice bad" role="alert" data-testid="content-error">{error}</p>}

      <h2>Minta naskah</h2>
      <form className="form" onSubmit={(e) => void submit(e)}>
        <label htmlFor="script-title">Judul video</label>
        <input id="script-title" value={draft.judul} maxLength={150}
          onChange={(e) => setDraft({ ...draft, judul: e.target.value })} />
        <label htmlFor="script-notes">Catatan (poin yang harus masuk, gaya, dll.)</label>
        <textarea id="script-notes" rows={4} maxLength={2000} value={draft.catatan}
          onChange={(e) => setDraft({ ...draft, catatan: e.target.value })} />
        <label htmlFor="script-format">Format</label>
        <select id="script-format" value={draft.format}
          onChange={(e) => setDraft({ ...draft, format: e.target.value as ContentFormat })}>
          <option value="panjang">Video panjang</option><option value="shorts">Shorts</option>
        </select>
        <label htmlFor="script-duration">Target durasi (opsional)</label>
        <input id="script-duration" value={draft.durasi} maxLength={40} placeholder="mis. 8 menit"
          onChange={(e) => setDraft({ ...draft, durasi: e.target.value })} />
        <button type="submit" className="primary" disabled={running || draft.judul.trim().length < 3}>Tulis naskah</button>
      </form>
      <TaskNotice task={task} />

      <h2>Draf tersimpan</h2>
      {items.length === 0 && <p className="muted" data-testid="scripts-empty">Belum ada draf naskah.</p>}
      {items.map((item) => (
        <details key={item.id} className="panel" data-testid="script-item">
          <summary>{item.payload.judul} <span className="muted">· {formatTime(item.created_at)}</span></summary>
          <p><strong>Hook:</strong> {item.payload.hook}</p>
          <div className="table-wrap">
            <table className="data-table storyboard" data-testid="storyboard">
              <thead><tr>
                <th scope="col">Bagian</th><th scope="col">Narasi</th><th scope="col">Visual</th><th scope="col">Durasi</th>
              </tr></thead>
              <tbody>
                {item.payload.bagian.map((b, i) => (
                  <tr key={`${i}-${b.judul}`}>
                    <td>{b.judul}</td><td>{b.narasi}</td><td>{b.visual || "—"}</td><td>{b.durasi || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {item.payload.cta && <p><strong>CTA:</strong> {item.payload.cta}</p>}
          <AiStamp item={item} />
          <button type="button" onClick={() => download(item)}>Unduh Markdown</button>{" "}
          <button type="button" onClick={() => void api.content.remove(item.id).catch((err) => setError(errorText(err, "Gagal menghapus.")))}>
            Hapus draf
          </button>
        </details>
      ))}
    </section>
  );
}
