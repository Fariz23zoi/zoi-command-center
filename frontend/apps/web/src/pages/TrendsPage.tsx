import { api, type ViralData } from "@zoi/api-client";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { errorText } from "../lib/youtube";
import { useApp } from "../stores/appStore";
import { AiStamp, PublicNote, Stamp, TaskNotice, useTaskWatch } from "./publicShared";
import { listLabel } from "./ViralPage";

/** Trend Detector: AI lokal membaca JUDUL dari satu daftar tersimpan dan mengelompokkannya. Bukan statistik. */
export function TrendsPage() {
  const revision = useApp((s) => s.youtubeRevision);
  const [params] = useSearchParams();
  const [data, setData] = useState<ViralData | null>(null);
  const [chosen, setChosen] = useState(params.get("key") ?? "");
  const [error, setError] = useState<string | null>(null);
  const { task, running, watch } = useTaskWatch();

  useEffect(() => {
    api.youtubePublic.viral().then(setData).catch((err) => setError(errorText(err, "Data tidak dapat dimuat.")));
  }, [revision]);

  const lists = data ? [...data.trending, ...data.searches] : [];
  const key = lists.some((l) => l.key === chosen) ? chosen : lists[0]?.key ?? "";

  async function start() {
    setError(null);
    try {
      watch(await api.youtubePublic.themes(key));
    } catch (err) {
      setError(errorText(err, "Tugas tidak dapat dimulai."));
    }
  }

  return (
    <section className="page" data-testid="trends-page">
      <h1>Trend Detector</h1>
      {data && <PublicNote info={data} />}
      <p className="notice warn" data-testid="themes-disclaimer">
        Rangkuman di halaman ini adalah interpretasi AI lokal atas judul video — bukan statistik, bukan peringkat, dan
        bukan data dari YouTube. AI hanya menerima judul, tanpa angka.
      </p>
      {error && <p className="notice bad" role="alert" data-testid="public-error">{error}</p>}

      <h2>Rangkum tema</h2>
      {data && lists.length === 0 ? (
        <p className="muted" data-testid="trends-empty">
          Belum ada daftar untuk dibaca. Ambil dulu di <Link to="/viral">Viral Video Hunter</Link>.
        </p>
      ) : (
        <div className="form">
          <label htmlFor="themes-source">Daftar</label>
          <select id="themes-source" value={key} onChange={(e) => setChosen(e.target.value)}>
            {data && lists.map((l) => <option key={l.key} value={l.key}>{listLabel(l.key, data)}</option>)}
          </select>
          <button type="button" className="primary" disabled={!key || running} data-testid="themes-start"
            onClick={() => void start()}>Rangkum tema (AI lokal)</button>
        </div>
      )}
      <TaskNotice task={task} />

      <h2>Rangkuman tersimpan</h2>
      {data && data.themes.length === 0 && <p className="muted">Belum ada rangkuman.</p>}
      {data?.themes.map((entry) => (
        <div key={entry.key} className="panel" data-testid="themes-entry">
          <h3>{listLabel(entry.payload.source_key, data)}</h3>
          <p className="muted">{entry.payload.label} Judul yang dibaca: {entry.payload.titles_read}.</p>
          {entry.payload.themes.length === 0 && <p className="muted">AI tidak mengembalikan tema.</p>}
          {entry.payload.themes.map((theme) => (
            <div key={theme.nama} data-testid="theme">
              <h4>{theme.nama}</h4>
              <p>{theme.penjelasan}</p>
              {theme.contoh_judul.length > 0 && <ul>{theme.contoh_judul.map((j) => <li key={j}>{j}</li>)}</ul>}
              {theme.contoh_dibuang > 0 && (
                <p className="muted">{theme.contoh_dibuang} contoh dari AI dibuang karena tidak ada di daftar.</p>
              )}
            </div>
          ))}
          <AiStamp item={entry.payload} />
          <Stamp info={data} fetchedAt={entry.fetched_at} expiresAt={entry.expires_at} />
          <Link to={`/ideas?tema=${encodeURIComponent(entry.payload.source_key)}`}>Pakai untuk ide konten</Link>
        </div>
      ))}
    </section>
  );
}
