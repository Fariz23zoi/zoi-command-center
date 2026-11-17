import { api, type UpdateStatus } from "@zoi/api-client";
import { Download, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { formatTime } from "../lib/format";
import { errorText } from "../lib/youtube";
import { Badge, Card } from "../ui";

const mb = (n: number | null) => (n ? `${(n / 1024 / 1024).toFixed(1)} MB` : "");

/** Settings › Update: cek versi baru di GitHub dan pasang dengan satu klik (ADR 0017). */
export function UpdatePage() {
  const [st, setSt] = useState<UpdateStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"check" | "install" | null>(null);

  useEffect(() => { api.update.status().then(setSt).catch((e) => setError(errorText(e, "Status update tidak dapat dimuat."))); }, []);

  async function run(kind: "check" | "install") {
    if (kind === "install" && !window.confirm(
      "Pasang update sekarang? ZOI akan berhenti sebentar (sekitar 1–3 menit, bisa lebih lama bila mengunduh paket Python), "
      + "lalu menyala lagi di jendela baru. Versi lama tetap disimpan.")) return;
    setBusy(kind);
    setError(null);
    try {
      setSt(await api.update[kind]());
    } catch (e) {
      setError(errorText(e, kind === "check" ? "Gagal mengecek update." : "Update gagal dipasang."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="page" data-testid="update-page">
      <p className="muted"><Link to="/settings">Settings</Link> › Update</p>
      <h1>Update ZOI</h1>
      {error && <p className="notice bad" role="alert">{error}</p>}
      {!st ? <p className="muted">Memuat…</p> : !st.enabled ? (
        <p className="notice warn">Update otomatis hanya untuk ZOI di laptop (mode local).</p>
      ) : (
        <>
          <Card title="Versi" action={
            <button type="button" onClick={() => run("check")} disabled={busy !== null}>
              <RefreshCw size={16} aria-hidden="true" /> {busy === "check" ? "Mengecek…" : "Cek sekarang"}
            </button>}>
            <p>Terpasang: <b data-testid="update-current">{st.current}</b>
              {st.latest && <> · Terbaru di GitHub: <b>{st.latest.version}</b></>}
              {" "}{st.update_available ? <Badge tone="primary">Update tersedia</Badge>
                : st.latest ? <Badge tone="ok">Sudah terbaru</Badge> : null}</p>
            <p className="muted">Dicek otomatis tiap 24 jam. Terakhir: {st.checked_at ? formatTime(st.checked_at) : "belum pernah"}
              {" "}· sumber: github.com/{st.repo}</p>
            {st.error && <p className="notice warn">{st.error}</p>}
          </Card>
          {st.update_available && st.latest && (
            <Card title={st.latest.name} highlight>
              {st.latest.notes && <pre className="update-notes">{st.latest.notes}</pre>}
              {st.phase === "applying" ? (
                <p className="notice ok" role="status">Update sedang dipasang di jendela baru. Halaman ini akan terputus sebentar;
                  buka lagi <b>Buka ZOI</b> bila browser tidak terbuka sendiri.</p>
              ) : (
                <button type="button" className="primary" onClick={() => run("install")}
                  disabled={busy !== null || !st.can_install} data-testid="update-install">
                  <Download size={16} aria-hidden="true" /> {busy === "install" ? "Mengunduh…" : `Update ke ${st.latest.version}`} {mb(st.latest.size)}
                </button>
              )}
              {st.install_note && <p className="muted">{st.install_note}</p>}
              <p className="muted">File dicocokkan dengan hash SHA-256 dari rilis yang sama. Versi baru dipasang di folder
                tersendiri; folder versi lama tidak dihapus, dan dinyalakan lagi otomatis bila pemasangan gagal.</p>
            </Card>
          )}
        </>
      )}
    </section>
  );
}

/** Pita kecil di atas halaman bila ada versi baru. */
export function UpdateBanner() {
  const [st, setSt] = useState<UpdateStatus | null>(null);
  useEffect(() => {
    const load = () => api.update.status().then(setSt).catch(() => undefined);
    load();
    const t = setInterval(load, 30 * 60 * 1000);
    return () => clearInterval(t);
  }, []);
  if (!st?.update_available || !st.latest) return null;
  return (
    <div className="update-banner" role="status" data-testid="update-banner">
      ZOI {st.latest.version} tersedia. <Link to="/settings/update">Lihat & pasang</Link>
    </div>
  );
}
