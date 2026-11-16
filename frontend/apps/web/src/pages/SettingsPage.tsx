import { api, ApiError, type Preferences } from "@zoi/api-client";
import { type FormEvent, useEffect, useState } from "react";

import { useApp } from "../stores/appStore";

export function SettingsPage() {
  const config = useApp((s) => s.config);
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => { api.preferences().then(setPrefs).catch(() => undefined); }, []);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!prefs) return;
    try {
      setPrefs(await api.savePreferences(prefs));
      setSaved("Preferensi disimpan.");
    } catch (err) {
      setSaved(err instanceof ApiError ? err.message : "Gagal menyimpan.");
    }
  }

  return (
    <section className="page">
      <h1>Settings</h1>
      <h2>Konfigurasi efektif</h2>
      <p className="muted">Hanya-baca. Diubah lewat file <code>.env</code>, lalu restart ZOI.</p>
      {config && (
        <dl className="kv" data-testid="config-list">
          <dt>Mode</dt><dd>{config.mode}</dd>
          <dt>Alamat</dt><dd>{config.base_url}</dd>
          <dt>Penyedia AI</dt><dd>{config.provider}{config.ollama_model ? ` · ${config.ollama_model}` : ""}</dd>
          <dt>Folder data</dt><dd className="wrap">{config.data_dir}</dd>
          <dt>Mode avatar</dt><dd>{config.avatar_mode}</dd>
          <dt>Versi</dt><dd>{config.version}</dd>
        </dl>
      )}

      <h2>Preferensi</h2>
      <p className="muted">Disimpan di database dan ikut berpindah saat data diekspor.</p>
      {prefs && (
        <form className="form" onSubmit={save}>
          <label htmlFor="pref-lang">Bahasa antarmuka</label>
          <select id="pref-lang" value={prefs.ui_language}
            onChange={(e) => setPrefs({ ...prefs, ui_language: e.target.value as Preferences["ui_language"] })}>
            <option value="id">Indonesia</option>
            <option value="en">English (menyusul)</option>
          </select>
          <label htmlFor="pref-avatar">Avatar pilihan</label>
          <select id="pref-avatar" value={prefs.avatar_mode_preference}
            onChange={(e) => setPrefs({ ...prefs, avatar_mode_preference: e.target.value as Preferences["avatar_mode_preference"] })}>
            <option value="auto">Otomatis</option>
            <option value="2d">2D (paling ringan)</option>
            <option value="3d">3D (Phase 2)</option>
          </select>
          <button type="submit" className="primary">Simpan preferensi</button>
          {saved && <p role="status" className="muted">{saved}</p>}
        </form>
      )}
    </section>
  );
}
