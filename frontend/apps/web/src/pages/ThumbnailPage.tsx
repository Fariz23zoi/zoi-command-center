import { api, type ProductionPackage } from "@zoi/api-client";
import { type ChangeEvent, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { errorText } from "../lib/youtube";
import {
  type Background, COLOR, drawThumbnail, type HookLine, type Kotak, loadFonts, type Rasio, SIZE, type ThumbSpec,
  type Ukuran, type Warna,
} from "../thumbnail/render";
import "../thumbnail/thumbnail.css";

const UKURAN: Ukuran[] = ["kecil", "sedang", "besar"];
const WARNA: Warna[] = ["hitam", "putih", "pink", "kuning"];
const KOTAK: Kotak[] = ["putih", "kuning", "hitam", "tanpa"];
const newSeed = () => Math.floor(Math.random() * 1_000_000_000);

/** Thumbnail otomatis: AI ZOI menulis teks hook, browser menyusun gambar (foto tidak diunggah ke mana pun). */
export function ThumbnailPage() {
  const [params] = useSearchParams();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [topik, setTopik] = useState("");
  const [rasio, setRasio] = useState<Rasio>("9:16");
  const [spec, setSpec] = useState<ThumbSpec | null>(null);
  const [bg, setBg] = useState<Background | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fontsOk, setFontsOk] = useState(true);

  // Dari halaman Produksi: ?paket=<id> → topik dari judul + isi beat, video paket bisa dipakai sebagai latar.
  useEffect(() => {
    const id = params.get("paket");
    if (!id) return;
    api.production.packages().then(async ({ items }) => {
      const pkg: ProductionPackage | undefined = items.find((p) => p.id === id);
      if (!pkg) return;
      if (pkg.rasio === "16:9") setRasio("16:9");
      let isi = "";
      try {
        const res = await fetch(api.production.fileUrl(id, "paket.json"));
        if (res.ok) {
          const data = (await res.json()) as { beats?: { n?: string }[] };
          isi = (data.beats ?? []).map((b) => b.n ?? "").filter(Boolean).slice(0, 4).join("\n");
        }
      } catch { /* judul saja sudah cukup */ }
      setTopik([pkg.judul, isi].filter(Boolean).join("\n\n").slice(0, 3000));
      if (pkg.files["video.mp4"]) setVideoUrl(api.production.fileUrl(id, "video.mp4"));
    }, () => undefined);
  }, [params]);

  useEffect(() => { loadFonts().then(setFontsOk, () => setFontsOk(false)); }, []);

  useEffect(() => {
    const ctx = canvasRef.current?.getContext("2d");
    if (!ctx || !spec) return;
    let alive = true;
    loadFonts().finally(() => { if (alive) drawThumbnail(ctx, spec, bg); });
    return () => { alive = false; };
  }, [spec, bg]);

  async function generate() {
    setError(null);
    setNote(null);
    setBusy(true);
    try {
      const hook = await api.thumbnail.hook(topik.trim(), rasio);
      setSpec((prev) => ({ baris: hook.baris, bubble: hook.bubble, aksen: hook.aksen, rasio, seed: newSeed(),
        posisi: prev?.posisi, fokus: prev?.fokus }));
      setNote(hook.is_mock ? "Penyedia AI adalah MOCK — teks tiruan, bukan dari AI." : `Teks hook dari AI ZOI (${hook.provider}).`);
    } catch (err) {
      setError(errorText(err, "AI ZOI gagal membuat teks hook."));
    } finally {
      setBusy(false);
    }
  }

  function pickFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const url = URL.createObjectURL(file);
    if (file.type.startsWith("video/")) {
      setVideoUrl(url);
      return;
    }
    const img = new Image();
    img.onload = () => setBg({ source: img, width: img.naturalWidth, height: img.naturalHeight });
    img.onerror = () => setError("Gambar tidak bisa dibuka.");
    img.src = url;
  }

  function useFrame() {
    const video = videoRef.current;
    if (!video || !video.videoWidth) { setError("Putar/geser video dulu ke bagian yang diinginkan."); return; }
    const frame = document.createElement("canvas");
    frame.width = video.videoWidth;
    frame.height = video.videoHeight;
    frame.getContext("2d")?.drawImage(video, 0, 0);
    setBg({ source: frame, width: frame.width, height: frame.height });
  }

  function changeRasio(next: Rasio) {
    setRasio(next);
    if (spec) setSpec({ ...spec, rasio: next });
  }

  function editLine(index: number, patch: Partial<HookLine>) {
    if (!spec) return;
    setSpec({ ...spec, baris: spec.baris.map((l, i) => (i === index ? { ...l, ...patch } : l)) });
  }

  function download() {
    canvasRef.current?.toBlob((blob) => {
      if (!blob) return;
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `thumbnail-zoi-${rasio.replace(":", "x")}.png`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    }, "image/png");
  }

  const [W, H] = SIZE[rasio];
  return (
    <section className="page thumb-page" data-testid="thumbnail-page">
      <h1>Thumbnail</h1>
      <p className="muted">
        AI ZOI menulis teks hook; gambar disusun di browser ini. Foto/video latarmu tidak diunggah ke mana pun,
        dan tidak ada yang dipublikasikan.
      </p>
      {error && <p className="notice bad" role="alert">{error}</p>}
      {!fontsOk && <p className="notice warn">Font thumbnail gagal dimuat — memakai font cadangan.</p>}

      <div className="thumb-grid">
        <div className="thumb-controls">
          <label htmlFor="thumb-topik">Topik / isi video</label>
          <textarea id="thumb-topik" rows={5} value={topik} maxLength={6000} data-testid="thumb-topik"
                    placeholder="Contoh: kenapa orang susah menolak permintaan teman"
                    onChange={(e) => setTopik(e.target.value)} />

          <div className="thumb-row" role="group" aria-label="Format">
            {(["9:16", "16:9"] as Rasio[]).map((r) => (
              <button key={r} type="button" className={rasio === r ? "primary" : ""} aria-pressed={rasio === r}
                      onClick={() => changeRasio(r)}>
                {r === "9:16" ? "9:16 Shorts" : "16:9 YouTube"}
              </button>
            ))}
          </div>

          <label htmlFor="thumb-file">Foto / video latar (opsional)</label>
          <input id="thumb-file" type="file" accept="image/*,video/*" onChange={pickFile} />
          {videoUrl && (
            <div className="thumb-video">
              <video ref={videoRef} src={videoUrl} controls preload="metadata" playsInline crossOrigin="anonymous" />
              <button type="button" onClick={useFrame}>Pakai frame ini sebagai latar</button>
            </div>
          )}
          {bg && <button type="button" className="ghost" onClick={() => setBg(null)}>Hapus latar</button>}
          {spec && (
            <>
              <div className="thumb-row" role="group" aria-label="Posisi teks">
                {(["atas", "bawah"] as const).map((pos) => (
                  <button key={pos} type="button" aria-pressed={(spec.posisi ?? "atas") === pos}
                          className={(spec.posisi ?? "atas") === pos ? "primary" : ""}
                          onClick={() => setSpec({ ...spec, posisi: pos })}>
                    Teks di {pos}
                  </button>
                ))}
              </div>
              {bg && (
                <label className="thumb-range">Geser latar
                  <input type="range" min={0} max={100} value={Math.round((spec.fokus ?? 0.5) * 100)}
                         onChange={(e) => setSpec({ ...spec, fokus: Number(e.target.value) / 100 })} />
                </label>
              )}
            </>
          )}

          <button type="button" className="primary thumb-go" disabled={busy || topik.trim().length < 3}
                  data-testid="thumb-generate" onClick={generate}>
            {busy ? "ZOI AI sedang menulis hook…" : "✨ Buat Thumbnail Otomatis"}
          </button>
          {note && <p className="muted">{note}</p>}

          {spec && (
            <>
              <h2>Edit teks</h2>
              {spec.baris.map((line, i) => (
                <div key={i} className="thumb-line" data-testid="thumb-line">
                  <input value={line.teks} maxLength={60} aria-label={`Baris ${i + 1}`}
                         onChange={(e) => editLine(i, { teks: e.target.value })} />
                  <select value={line.ukuran} aria-label="Ukuran" onChange={(e) => editLine(i, { ukuran: e.target.value as Ukuran })}>
                    {UKURAN.map((v) => <option key={v} value={v}>{v}</option>)}
                  </select>
                  <select value={line.warna} aria-label="Warna teks" onChange={(e) => editLine(i, { warna: e.target.value as Warna })}>
                    {WARNA.map((v) => <option key={v} value={v}>{v}</option>)}
                  </select>
                  <select value={line.kotak} aria-label="Kotak" onChange={(e) => editLine(i, { kotak: e.target.value as Kotak })}
                          style={{ borderLeft: `6px solid ${COLOR[line.kotak] === "transparent" ? "#666" : COLOR[line.kotak]}` }}>
                    {KOTAK.map((v) => <option key={v} value={v}>kotak {v}</option>)}
                  </select>
                </div>
              ))}
              <label htmlFor="thumb-bubble">Bubble reaksi (pisahkan dengan | )</label>
              <input id="thumb-bubble" value={spec.bubble.join(" | ")}
                     onChange={(e) => setSpec({ ...spec, bubble: e.target.value.split("|").map((s) => s.trim()).filter(Boolean).slice(0, 2) })} />
              <div className="thumb-row">
                <button type="button" onClick={() => setSpec({ ...spec, seed: newSeed() })}>🎲 Acak gaya</button>
                <button type="button" onClick={() => setSpec({ ...spec, aksen: spec.aksen === "pink" ? "kuning" : "pink" })}>
                  Ganti aksen
                </button>
                <button type="button" className="primary" data-testid="thumb-download" onClick={download}>Unduh PNG</button>
              </div>
            </>
          )}
        </div>

        <div className={`thumb-preview r${rasio.replace(":", "x")}`}>
          {spec
            ? <canvas ref={canvasRef} width={W} height={H} data-testid="thumb-canvas" aria-label="Pratinjau thumbnail" />
            : <p className="empty">Isi topik lalu klik <b>Buat Thumbnail Otomatis</b>. Hasil {W}×{H} PNG.</p>}
        </div>
      </div>
    </section>
  );
}
