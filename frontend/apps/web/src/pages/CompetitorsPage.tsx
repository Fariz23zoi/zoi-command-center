import { api, type CompetitorsData } from "@zoi/api-client";
import { type FormEvent, useEffect, useState } from "react";

import { errorText, exact } from "../lib/youtube";
import { useApp } from "../stores/appStore";
import { PublicNote, Stamp, VideoTable } from "./publicShared";

/** Competitor Intelligence: data publik channel pantauan, apa adanya. Tanpa skor, tanpa riwayat jangka panjang. */
export function CompetitorsPage() {
  const revision = useApp((s) => s.youtubeRevision);
  const [data, setData] = useState<CompetitorsData | null>(null);
  const [draft, setDraft] = useState({ ref: "", note: "" });
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.youtubePublic.competitors().then(setData)
      .catch((err) => setError(errorText(err, "Daftar pantauan tidak dapat dimuat.")));
  }, [revision]);

  async function run(label: string, action: () => Promise<CompetitorsData>) {
    setBusy(label);
    setError(null);
    try {
      setData(await action());
      return true;
    } catch (err) {
      setError(errorText(err, "Permintaan gagal."));
      return false;
    } finally {
      setBusy(null);
    }
  }

  async function add(event: FormEvent) {
    event.preventDefault();
    if (await run("add", () => api.youtubePublic.addCompetitor(draft.ref, draft.note))) setDraft({ ref: "", note: "" });
  }

  return (
    <section className="page" data-testid="competitors-page">
      <h1>Competitor Intelligence</h1>
      {data && <PublicNote info={data} />}
      {error && <p className="notice bad" role="alert" data-testid="public-error">{error}</p>}

      <h2>Tambah channel pantauan</h2>
      <form className="form" onSubmit={(e) => void add(e)}>
        <label htmlFor="competitor-ref">Handle, ID, atau tautan channel</label>
        <input id="competitor-ref" value={draft.ref} maxLength={300} placeholder="@namachannel"
          onChange={(e) => setDraft({ ...draft, ref: e.target.value })} />
        <label htmlFor="competitor-note">Catatanmu (opsional)</label>
        <input id="competitor-note" value={draft.note} maxLength={200}
          onChange={(e) => setDraft({ ...draft, note: e.target.value })} />
        <button type="submit" className="primary" disabled={!data?.connected || busy !== null || draft.ref.trim().length < 3}>
          Tambah channel
        </button>
        <span className="muted">Memakai 1 unit kuota. Maksimal {data?.max ?? "—"} channel.</span>
      </form>

      <h2>Channel pantauan</h2>
      {data && data.items.length === 0 && <p className="muted" data-testid="competitors-empty">Belum ada channel pantauan.</p>}
      {data?.items.map((item) => {
        const entry = item.data;
        const channel = entry?.payload.channel;
        return (
          <div key={item.channel_id} className="panel" data-testid="competitor-item">
            <h3>{channel ? `${channel.title}${channel.custom_url ? ` · ${channel.custom_url}` : ""}` : item.channel_id}</h3>
            {item.note && <p className="muted">Catatanmu: {item.note}</p>}
            {channel && entry ? (
              <>
                <dl className="kv">
                  <dt>Subscriber</dt>
                  <dd>{channel.hidden_subscribers ? "disembunyikan di channel" : exact(channel.subscriber_count)}</dd>
                  <dt>Total tayangan</dt><dd>{exact(channel.view_count)}</dd>
                  <dt>Jumlah video</dt><dd>{exact(channel.video_count)}</dd>
                </dl>
                {entry.payload.videos
                  ? <VideoTable videos={entry.payload.videos} testId="competitor-videos" showChannel={false} />
                  : <p className="muted">Video terbaru belum diambil.</p>}
                <Stamp info={data} fetchedAt={entry.fetched_at} expiresAt={entry.expires_at} />
              </>
            ) : (
              <p className="muted" data-testid="competitor-expired">
                Data channel ini sudah dihapus (lebih dari {data.retention_days} hari). Ambil lagi bila masih perlu.
              </p>
            )}
            <button type="button" disabled={!data.connected || busy !== null}
              onClick={() => void run(item.channel_id, () => api.youtubePublic.refreshCompetitor(item.channel_id))}>
              {busy === item.channel_id ? "Mengambil…" : "Ambil data terbaru (3 unit)"}
            </button>{" "}
            <button type="button" disabled={busy !== null}
              onClick={() => void run(item.channel_id, () => api.youtubePublic.removeCompetitor(item.channel_id))}>
              Hapus dari pantauan
            </button>
          </div>
        );
      })}
    </section>
  );
}
