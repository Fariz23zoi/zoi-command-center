import { api, type ContentFormat, type IdeaSet } from "@zoi/api-client";
import { type FormEvent, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { formatTime } from "../lib/format";
import { errorText } from "../lib/youtube";
import { useApp } from "../stores/appStore";
import { AiStamp, TaskNotice, useTaskWatch } from "./publicShared";

/** Content Ideas: draf ide oleh AI lokal. Konteks: memori + judul video channel sendiri (tanpa angka). */
export function IdeasPage() {
  const revision = useApp((s) => s.contentRevision);
  const [params] = useSearchParams();
  const themeKey = params.get("tema");
  const [items, setItems] = useState<IdeaSet[]>([]);
  const [mock, setMock] = useState(false);
  const [draft, setDraft] = useState({ topik: "", format: "panjang" as ContentFormat, jumlah: 3, pakai_channel: true });
  const [useTheme, setUseTheme] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { task, running, watch } = useTaskWatch();

  useEffect(() => {
    api.content.ideas().then((r) => { setItems(r.items); setMock(r.is_mock); })
      .catch((err) => setError(errorText(err, "Draf ide tidak dapat dimuat.")));
  }, [revision]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      watch(await api.content.makeIdeas({ ...draft, topik: draft.topik.trim(), tema_key: themeKey && useTheme ? themeKey : null }));
    } catch (err) {
      setError(errorText(err, "Tugas tidak dapat dimulai."));
    }
  }

  async function remove(id: string) {
    try {
      await api.content.remove(id);
    } catch (err) {
      setError(errorText(err, "Gagal menghapus."));
    }
  }

  return (
    <section className="page" data-testid="ideas-page">
      <h1>Content Ideas</h1>
      {mock && (
        <p className="notice warn" data-testid="content-mock-banner">
          Mode development: penyedia AI adalah MOCK. Hasil di sini teks tiruan, bukan ide dari AI.
        </p>
      )}
      <p className="muted">
        Ide disusun AI lokal di komputer ini. ZOI tidak mengirim angka channel ke AI dan tidak mempublikasikan apa pun.
      </p>
      {error && <p className="notice bad" role="alert" data-testid="content-error">{error}</p>}

      <h2>Minta ide</h2>
      <form className="form" onSubmit={(e) => void submit(e)}>
        <label htmlFor="idea-topic">Topik atau arahan</label>
        <textarea id="idea-topic" rows={3} maxLength={500} value={draft.topik}
          onChange={(e) => setDraft({ ...draft, topik: e.target.value })} />
        <label htmlFor="idea-format">Format</label>
        <select id="idea-format" value={draft.format}
          onChange={(e) => setDraft({ ...draft, format: e.target.value as ContentFormat })}>
          <option value="panjang">Video panjang</option><option value="shorts">Shorts</option>
        </select>
        <label htmlFor="idea-count">Jumlah ide</label>
        <select id="idea-count" value={draft.jumlah} onChange={(e) => setDraft({ ...draft, jumlah: Number(e.target.value) })}>
          {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
        <label><input type="checkbox" checked={draft.pakai_channel}
          onChange={(e) => setDraft({ ...draft, pakai_channel: e.target.checked })} /> Beri AI judul video channel-ku sebagai konteks</label>
        {themeKey && (
          <label><input type="checkbox" checked={useTheme} data-testid="idea-use-theme"
            onChange={(e) => setUseTheme(e.target.checked)} /> Sertakan rangkuman tema yang dipilih di Trend Detector</label>
        )}
        <button type="submit" className="primary" disabled={running || draft.topik.trim().length < 3}>Susun ide</button>
      </form>
      <TaskNotice task={task} />

      <h2>Draf tersimpan</h2>
      {items.length === 0 && <p className="muted" data-testid="ideas-empty">Belum ada draf ide.</p>}
      {items.map((set) => (
        <div key={set.id} className="panel" data-testid="idea-set">
          <h3>{set.title}</h3>
          <p className="muted">{formatTime(set.created_at)} · {set.request.format === "shorts" ? "Shorts" : "Video panjang"}</p>
          {set.payload.ide.map((idea) => (
            <div key={idea.judul} data-testid="idea">
              <h4>{idea.judul}</h4>
              <p><strong>Hook:</strong> {idea.hook}</p>
              <p>{idea.garis_besar}</p>
              {idea.cta && <p><strong>CTA:</strong> {idea.cta}</p>}
              <Link to={`/script?judul=${encodeURIComponent(idea.judul)}&catatan=${encodeURIComponent(idea.garis_besar)}&format=${set.request.format}`}>
                Tulis naskah dari ide ini
              </Link>
            </div>
          ))}
          <AiStamp item={set} />
          <button type="button" onClick={() => void remove(set.id)}>Hapus draf</button>
        </div>
      ))}
    </section>
  );
}
