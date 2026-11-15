import { OnlineNotice } from "./OnlineNotice";
import { api, ApiError, type VoicePreferences, type VoiceStatus } from "@zoi/api-client";
import { type FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { speechSupported, whenVoicesReady } from "../lib/voice/browserVoices";
import { speakSample, stopReading } from "../lib/voice/session";
import { useApp } from "../stores/appStore";

const SAMPLE = "Halo, saya ZOI. Ini contoh suara saya untuk membacakan jawaban.";

/** Settings › Suara. Rekaman tidak disimpan; ZOI tidak mengunduh model suara. */
export function VoicePage() {
  const status = useApp((s) => s.voiceStatus);
  const stored = useApp((s) => s.voicePrefs);
  const [draft, setDraft] = useState<VoicePreferences | null>(null);
  const [notice, setNotice] = useState<{ kind: "ok" | "bad"; text: string } | null>(null);
  const [voices, setVoices] = useState<{ name: string; lang: string }[]>([]);
  const prefs = draft ?? stored;

  useEffect(() => {
    api.voice.status().then(useApp.getState().setVoiceStatus).catch(() => undefined);
    whenVoicesReady().then((list) => setVoices(list.map((v) => ({ name: v.name, lang: v.lang }))));
  }, []);

  if (!status || !prefs) return <section className="page"><p className="muted">Memuat…</p></section>;

  const update = (patch: Partial<VoicePreferences>) => setDraft({ ...prefs, ...patch });

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!prefs) return;
    try {
      useApp.getState().setVoicePrefs(await api.voice.savePreferences(prefs));
      setDraft(null);
      useApp.getState().setVoiceStatus(await api.voice.status());
      setNotice({ kind: "ok", text: "Preferensi suara disimpan." });
    } catch (err) {
      setNotice({ kind: "bad", text: err instanceof ApiError ? err.message : "Gagal menyimpan." });
    }
  }

  function trySample() {
    if (draft) {
      setNotice({ kind: "bad", text: "Simpan preferensi dulu, lalu coba suara." });
      return;
    }
    setNotice(null);
    speakSample(SAMPLE);
  }

  const piperReal = status.tts.name === "piper";
  return (
    <section className="page" data-testid="voice-page">
      <p className="muted"><Link to="/settings">Settings</Link> › Suara</p>
      <h1>Suara</h1>
      <OnlineNotice feature="Fitur suara (Whisper/Piper)" />
      <p className="muted">
        Rekaman suaramu hanya dikirim ke ZOI di komputer ini, diproses, lalu <strong>dibuang — tidak disimpan</strong>.
        Tidak ada layanan suara cloud. ZOI tidak mengunduh model suara; pemasangan dilakukan sendiri lewat perintah.
      </p>
      {notice && <p className={`notice ${notice.kind}`} role="status" data-testid="voice-notice">{notice.text}</p>}

      <h2>Status</h2>
      <dl className="kv" data-testid="voice-status">
        <dt>Pengenal suara</dt>
        <dd>
          <span className={`badge ${status.stt.available ? "ok" : "bad"}`}>{status.stt.available ? "siap" : "tidak tersedia"}</span>{" "}
          {status.stt.detail}
        </dd>
        <dt>Suara Piper</dt>
        <dd>
          <span className={`badge ${status.tts.available ? "ok" : "bad"}`}>{status.tts.available ? "siap" : "tidak tersedia"}</span>{" "}
          {status.tts.detail}
        </dd>
        <dt>Yang membacakan jawaban</dt>
        <dd data-testid="reply-engine">
          {status.reply_engine === "piper" ? "Piper (avatar 3D bisa lip-sync)" : "Suara lokal browser/Windows (tanpa lip-sync)"}
        </dd>
      </dl>

      <h2>Preferensi</h2>
      <form className="form" onSubmit={save}>
        <label htmlFor="voice-lang">Bahasa yang kamu ucapkan</label>
        <select id="voice-lang" value={prefs.language} onChange={(e) => update({ language: e.target.value as VoicePreferences["language"] })}>
          <option value="id">Indonesia</option>
          <option value="en">English</option>
          <option value="auto">Deteksi otomatis</option>
        </select>

        <label className="check">
          <input type="checkbox" checked={prefs.speak_replies} onChange={(e) => update({ speak_replies: e.target.checked })} />
          Bacakan jawaban ZOI
        </label>
        <label className="check">
          <input type="checkbox" checked={prefs.auto_send} onChange={(e) => update({ auto_send: e.target.checked })} />
          Kirim otomatis setelah selesai bicara (bila mati: teks masuk kotak pesan untuk diperiksa)
        </label>

        <label htmlFor="voice-engine">Mesin suara</label>
        <select id="voice-engine" value={prefs.tts_engine}
          onChange={(e) => update({ tts_engine: e.target.value as VoicePreferences["tts_engine"] })}>
          <option value="auto">Otomatis (Piper bila siap & lisensi diterima, selain itu suara lokal)</option>
          <option value="piper">Piper</option>
          <option value="browser">Suara lokal browser/Windows</option>
        </select>

        <label htmlFor="voice-browser">Suara lokal</label>
        {!speechSupported() ? <p className="muted">Browser ini tidak mendukung suara lokal.</p>
          : voices.length === 0 ? (
            <p className="muted" data-testid="no-local-voices">{status.catalog.browser.note}</p>
          ) : (
            <select id="voice-browser" value={prefs.browser_voice ?? ""}
              onChange={(e) => update({ browser_voice: e.target.value || null })}>
              <option value="">Otomatis (Bahasa Indonesia bila ada)</option>
              {voices.map((v) => <option key={v.name} value={v.name}>{v.name} · {v.lang}</option>)}
            </select>
          )}

        <label htmlFor="voice-rate">Kecepatan bicara: {prefs.speech_rate.toFixed(2)}×</label>
        <input id="voice-rate" type="range" min={0.5} max={2} step={0.05} value={prefs.speech_rate}
          onChange={(e) => update({ speech_rate: Number(e.target.value) })} />

        {piperReal && (
          <div className="notice warn" data-testid="piper-license">
            <strong>Catatan lisensi suara Piper Bahasa Indonesia ({status.catalog.piper.voice})</strong>
            <p>{status.catalog.piper.license_note}</p>
            <label className="check">
              <input type="checkbox" checked={prefs.piper_license_accepted}
                onChange={(e) => update({ piper_license_accepted: e.target.checked })} />
              Saya mengerti dan memakai suara ini hanya untuk pemakaian pribadi
            </label>
          </div>
        )}

        <div className="row">
          <button type="submit" className="primary" disabled={!draft}>Simpan preferensi</button>
          <button type="button" onClick={trySample}>Coba suara</button>
          <button type="button" onClick={stopReading}>Hentikan</button>
        </div>
      </form>

      <InstallSection status={status} />
    </section>
  );
}

function InstallSection({ status }: { status: VoiceStatus }) {
  const { whisper, piper } = status.catalog;
  return (
    <>
      <h2>Cara memasang (dilakukan sendiri)</h2>
      <h3>Pengenal suara — {whisper.package}</h3>
      <p className="muted">{whisper.note}</p>
      <ul className="model-list" data-testid="whisper-models">
        {whisper.models.map((m) => (
          <li key={m.name} className="model-item">
            <div className="model-head"><strong>{m.name}</strong><span className="badge">{m.download}</span></div>
            <p className="model-fit">{m.fit}</p>
          </li>
        ))}
      </ul>
      <ol className="commands">{whisper.install.map((c) => <li key={c}><code className="command">{c}</code></li>)}</ol>
      <h3>Suara — {piper.package}</h3>
      <p className="muted">Suara {piper.voice}, unduhan {piper.download}. Baca catatan lisensinya di atas sebelum memakai.</p>
      <ol className="commands">{piper.install.map((c) => <li key={c}><code className="command">{c}</code></li>)}</ol>
    </>
  );
}
