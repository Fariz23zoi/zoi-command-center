import { api, ApiError, type Preferences } from "@zoi/api-client";
import { clearCachedFps, readCachedFps } from "@zoi/avatar";
import { type ChangeEvent, type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { avatarController } from "../lib/avatarBridge";
import { useApp } from "../stores/appStore";

export function SettingsPage() {
  const config = useApp((s) => s.config);
  const stored = useApp((s) => s.prefs);
  const renderer = useApp((s) => s.avatarRenderer);
  const avatarNote = useApp((s) => s.avatarNote);
  const [draft, setDraft] = useState<Preferences | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [lipsync, setLipsync] = useState<string | null>(null);
  const [fps, setFps] = useState(() => readCachedFps());
  const prefs = draft ?? stored;
  const serverForces2D = config?.avatar_mode === "2d";

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!prefs) return;
    try {
      useApp.getState().setPrefs(await api.savePreferences(prefs));
      setDraft(null);
      setSaved("Preferensi disimpan.");
    } catch (err) {
      setSaved(err instanceof ApiError ? err.message : "Gagal menyimpan.");
    }
  }

  function retest() {
    clearCachedFps();
    setFps(null);
    setSaved("Hasil uji perangkat dihapus. Avatar 3D diuji ulang saat halaman dimuat ulang (mode Otomatis).");
  }

  async function testLipsync(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const avatar = avatarController.current;
    if (!avatar || avatar.renderer !== "3d") {
      setLipsync("Lip-sync hanya tersedia saat avatar 3D aktif.");
      return;
    }
    setLipsync(`Memutar "${file.name}"…`);
    try {
      await avatar.speak(file); // file dibaca di browser ini saja — tidak dikirim ke server
      setLipsync(`Selesai memutar "${file.name}".`);
    } catch (err) {
      setLipsync(`Gagal memutar audio: ${(err as Error).message}`);
    }
  }

  return (
    <section className="page">
      <h1>Settings</h1>
      <p className="notice ok">
        <Link to="/settings/ai" data-testid="ai-local-link">AI Lokal</Link> — status Ollama, model terpasang, model aktif,
        dan uji kecocokan model.
        {" · "}<Link to="/settings/voice" data-testid="voice-link">Suara</Link> — input suara, membacakan jawaban, dan
        cara memasang model suara.
        {" · "}<Link to="/settings/ai-cloud" data-testid="ai-cloud-link">AI Cloud</Link> — NVIDIA NIM dan OpenRouter (gratis,
        opsional): API key, uji model, batas permintaan, dan data yang dikirim.
        {" · "}<Link to="/settings/update">Update</Link> — cek & pasang versi baru ZOI
        {" · "}<Link to="/settings/youtube" data-testid="youtube-link">YouTube</Link> — hubungkan channel-mu (hanya-baca),
        kuota, dan hapus data.
      </p>
      <h2>Konfigurasi efektif</h2>
      <p className="muted">Hanya-baca. Diubah lewat file <code>.env</code>, lalu restart ZOI.</p>
      {config && (
        <dl className="kv" data-testid="config-list">
          <dt>Mode</dt><dd>{config.mode}</dd>
          <dt>Alamat</dt><dd>{config.base_url}</dd>
          <dt>Penyedia AI</dt><dd>{config.provider}{config.ollama_model ? ` · ${config.ollama_model}` : ""}</dd>
          <dt>Folder data</dt><dd className="wrap">{config.data_dir}</dd>
          <dt>Mode avatar (server)</dt><dd>{config.avatar_mode}</dd>
          <dt>Versi</dt><dd>{config.version}</dd>
        </dl>
      )}

      <h2>Preferensi</h2>
      <p className="muted">Disimpan di database dan ikut berpindah saat data diekspor.</p>
      {prefs && (
        <form className="form" onSubmit={save}>
          <label htmlFor="pref-lang">Bahasa antarmuka</label>
          <select id="pref-lang" value={prefs.ui_language}
            onChange={(e) => setDraft({ ...prefs, ui_language: e.target.value as Preferences["ui_language"] })}>
            <option value="id">Indonesia</option>
            <option value="en">English (menyusul)</option>
          </select>
          <label htmlFor="pref-avatar">Avatar</label>
          <select id="pref-avatar" value={prefs.avatar_mode_preference} disabled={serverForces2D}
            onChange={(e) => setDraft({ ...prefs, avatar_mode_preference: e.target.value as Preferences["avatar_mode_preference"] })}>
            <option value="auto">Otomatis (3D bila perangkat mampu)</option>
            <option value="2d">2D (paling ringan)</option>
            <option value="3d">3D</option>
          </select>
          {serverForces2D && <p className="muted">Server memaksa 2D (ZOI_AVATAR_MODE=2d) — cocok untuk perangkat lemah.</p>}
          <label htmlFor="pref-character">Karakter 3D</label>
          <select id="pref-character" value={prefs.avatar_character}
            onChange={(e) => setDraft({ ...prefs, avatar_character: e.target.value as Preferences["avatar_character"] })}>
            <option value="female">Perempuan</option>
            <option value="male">Laki-laki</option>
          </select>
          <button type="submit" className="primary">Simpan preferensi</button>
          {saved && <p role="status" className="muted">{saved}</p>}
        </form>
      )}

      <h2>Avatar</h2>
      <dl className="kv" data-testid="avatar-status">
        <dt>Renderer aktif</dt><dd data-testid="avatar-renderer">{renderer ?? "—"}</dd>
        <dt>Uji perangkat</dt><dd>{fps === null ? "belum ada" : `±${Math.round(fps)} fps`}</dd>
      </dl>
      {avatarNote && <p className="notice warn">{avatarNote}</p>}
      <p className="muted">
        Avatar 3D: wajah Microsoft Rocketbox (MIT) dengan lip-sync, kedip, dan alis. Gerak kepala, arah pandang, dan
        ekspresi senyum/cemberut <strong>belum tersedia</strong> — status ditunjukkan cincin warna dan label.
      </p>
      <div className="row">
        <button type="button" onClick={retest}>Uji ulang perangkat</button>
      </div>
      <label htmlFor="lipsync-file">Uji lip-sync dengan file audio dari perangkat ini</label>
      <input id="lipsync-file" type="file" accept="audio/*" onChange={testLipsync} disabled={renderer !== "3d"} />
      <p className="muted">File diputar di browser ini saja dan tidak dikirim ke server. Suara ZOI sendiri dibuat di Phase 4.</p>
      {lipsync && <p role="status" data-testid="lipsync-status">{lipsync}</p>}

      <BackupBlock />

      {config?.online && (
        <div className="settings-block">
          <h2>Sesi</h2>
          <p className="muted">ZOI online dilindungi satu kata sandi. Keluar menutup sesi di perangkat ini saja.</p>
          <button type="button" onClick={() => { api.auth.logout().finally(() => location.reload()); }}>
            Keluar
          </button>{" "}
          <button type="button" className="danger" title="Semua perangkat harus masuk lagi"
                  onClick={() => { api.auth.logoutAll().finally(() => location.reload()); }}>
            Keluar dari semua perangkat
          </button>
        </div>
      )}
    </section>
  );
}

/** Unduh/pulihkan cadangan data (zoi.backup/v2). Rahasia & kata sandi tidak pernah ikut. */
function BackupBlock() {
  const [file, setFile] = useState<File | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const restore = () => {
    if (!file) return;
    setBusy(true);
    setMessage(null);
    api.backup.restore(file).then(
      (r) => { setMessage({ ok: true, text: r.note }); setConfirm(false); setFile(null); },
      (e: unknown) => setMessage({ ok: false, text: e instanceof Error ? e.message : "Gagal memulihkan." }),
    ).finally(() => setBusy(false));
  };

  return (
    <div className="settings-block" data-testid="backup-block">
      <h2>Cadangan data</h2>
      <p className="muted">
        Satu file .zip berisi seluruh data ZOI (chat, memori, tugas, draf, data YouTube). API key, akun YouTube, dan
        kata sandi <strong>tidak pernah</strong> ikut — setelah memulihkan, hubungkan ulang bila perlu.
      </p>
      <a className="button" href={api.backup.downloadUrl} download data-testid="backup-download">Unduh cadangan</a>
      <label className="form">
        <span>Pulihkan dari file cadangan (.zip)</span>
        <input type="file" accept=".zip,application/zip" data-testid="backup-file"
               onChange={(e) => { setFile(e.target.files?.[0] ?? null); setConfirm(false); }} />
      </label>
      {file && !confirm && (
        <button type="button" onClick={() => setConfirm(true)}>Pulihkan dari {file.name}</button>
      )}
      {file && confirm && (
        <div className="notice warn">
          Semua data saat ini akan <strong>diganti</strong> isi file ini.{" "}
          <button type="button" disabled={busy} data-testid="backup-restore" onClick={restore}>
            {busy ? "Memulihkan…" : "Ya, ganti data"}
          </button>{" "}
          <button type="button" onClick={() => setConfirm(false)}>Batal</button>
        </div>
      )}
      {message && <p className={`notice ${message.ok ? "ok" : "bad"}`} role="status">{message.text}</p>}
    </div>
  );
}
