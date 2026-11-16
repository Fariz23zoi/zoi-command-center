import { api, type ViralData } from "@zoi/api-client";
import { type FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { errorText, exact } from "../lib/youtube";
import { useApp } from "../stores/appStore";
import { PublicNote, Stamp, VideoTable } from "./publicShared";

export function listLabel(key: string, data: ViralData): string {
  const search = data.searches.find((s) => s.key === key);
  if (search) return `Pencarian: “${search.payload.query}”`;
  const trending = data.trending.find((t) => t.key === key);
  const category = trending?.payload.category_id;
  const name = category ? data.categories?.payload.find((c) => c.id === category)?.title ?? `kategori ${category}` : null;
  return name ? `Trending Indonesia · ${name}` : "Trending Indonesia · semua kategori";
}

/** Viral Video Hunter: Trending resmi YouTube Indonesia + pencarian. Urutan dari YouTube, bukan skor ZOI. */
export function ViralPage() {
  const revision = useApp((s) => s.youtubeRevision);
  const [data, setData] = useState<ViralData | null>(null);
  const [category, setCategory] = useState("");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.youtubePublic.viral().then(setData).catch((err) => setError(errorText(err, "Data tidak dapat dimuat.")));
  }, [revision]);

  async function run(action: () => Promise<ViralData>) {
    setBusy(true);
    setError(null);
    try {
      setData(await action());
    } catch (err) {
      setError(errorText(err, "Permintaan gagal."));
    } finally {
      setBusy(false);
    }
  }

  function search(event: FormEvent) {
    event.preventDefault();
    void run(() => api.youtubePublic.search(query)).then(() => setQuery(""));
  }

  const lists = data ? [...data.trending, ...data.searches] : [];

  return (
    <section className="page" data-testid="viral-page">
      <h1>Viral Video Hunter</h1>
      {data && <PublicNote info={data} />}
      {error && <p className="notice bad" role="alert" data-testid="public-error">{error}</p>}

      <h2>Trending resmi YouTube Indonesia</h2>
      <div className="form">
        <label htmlFor="trending-category">Kategori</label>
        <select id="trending-category" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">Semua kategori</option>
          {data?.categories?.payload.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
        </select>
        <button type="button" className="primary" disabled={!data?.connected || busy} data-testid="trending-fetch"
          onClick={() => void run(() => api.youtubePublic.trending(category || null))}>
          Ambil Trending
        </button>
        <span className="muted">Memakai 1 unit kuota. Daftar kategori muncul setelah pengambilan pertama.</span>
      </div>

      <h2>Cari video</h2>
      <form className="form" onSubmit={search}>
        <label htmlFor="viral-query">Kata kunci</label>
        <input id="viral-query" value={query} maxLength={100} onChange={(e) => setQuery(e.target.value)} />
        <button type="submit" disabled={!data?.connected || busy || query.trim().length < 2}>Cari di YouTube</button>
        {data && (
          <span className="muted" data-testid="search-quota">
            Pencarian hari ini: {exact(data.quota.search_used)} dari batas aman {exact(data.quota.search_limit)}{" "}
            (batas resmi {exact(data.quota.search_official)}). Hasil pencarian tidak memuat angka tayangan.
          </span>
        )}
      </form>

      <h2>Daftar tersimpan</h2>
      {data && lists.length === 0 && <p className="muted" data-testid="viral-empty">Belum ada daftar. Ambil Trending atau cari kata kunci.</p>}
      {data && lists.map((entry) => (
        <div key={entry.key} className="panel" data-testid="viral-list">
          <h3>{listLabel(entry.key, data)}</h3>
          <p className="muted">Urutan persis seperti dikirim YouTube.</p>
          <VideoTable videos={entry.payload.items} testId="viral-videos" />
          <Stamp info={data} fetchedAt={entry.fetched_at} expiresAt={entry.expires_at} />
          <Link to={`/trends?key=${encodeURIComponent(entry.key)}`}>Rangkum tema judul</Link>{" · "}
          <button type="button" className="link" disabled={busy}
            onClick={() => void run(() => api.youtubePublic.removeList(entry.key))}>Hapus daftar</button>
        </div>
      ))}
    </section>
  );
}
