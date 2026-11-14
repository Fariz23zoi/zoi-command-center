import {
  type AiStatus, api, ApiError, type EvaluationInfo, type InstalledModel, type ModelDetails,
} from "@zoi/api-client";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { formatBytes, formatTime } from "../lib/format";
import { useApp } from "../stores/appStore";

const SOURCE_LABEL = { ui: "dipilih di halaman ini", env: "dari ZOI_OLLAMA_MODEL (.env)", none: "belum ada" } as const;
const ACTIVE_TASK = new Set(["QUEUED", "RUNNING"]);

function errorText(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

/** Settings › AI Lokal. Semua angka berasal dari Ollama di mesin ini; ZOI tidak pernah mengunduh atau menghapus model. */
export function AiLocalPage() {
  const revision = useApp((s) => s.aiRevision);
  const tasks = useApp((s) => s.tasks);
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ kind: "ok" | "bad"; text: string } | null>(null);
  const [details, setDetails] = useState<Record<string, ModelDetails | string>>({});
  const [evaluations, setEvaluations] = useState<EvaluationInfo[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const evalTasks = tasks.filter((t) => t.kind === "model_eval");
  const finishedEvalCount = evalTasks.filter((t) => t.status === "COMPLETED").length;
  const runningEval = evalTasks.find((t) => ACTIVE_TASK.has(t.status));

  const load = useCallback(() => {
    api.ai.status().then((s) => { setStatus(s); setLoadError(null); })
      .catch((err) => setLoadError(errorText(err, "Status AI tidak dapat dimuat.")));
  }, []);

  useEffect(() => { load(); }, [load, revision]);
  useEffect(() => {
    api.ai.evaluations().then((r) => setEvaluations(r.evaluations)).catch(() => setEvaluations([]));
  }, [finishedEvalCount]);

  async function act(key: string, action: () => Promise<string>) {
    setBusy(key);
    setNotice(null);
    try {
      setNotice({ kind: "ok", text: await action() });
    } catch (err) {
      setNotice({ kind: "bad", text: errorText(err, "Permintaan gagal.") });
    } finally {
      setBusy(null);
    }
  }

  const refreshProvider = () => api.providerStatus().then(useApp.getState().setProvider).catch(() => undefined);

  const testConnection = () => act("test", async () => {
    const result = await api.ai.test();
    if (!result.ok) throw new ApiError(502, result.detail);
    return `${result.detail} Waktu respons ${result.latency_ms} ms.`;
  });
  const makeActive = (model: string) => act(`active:${model}`, async () => {
    await api.ai.setActive(model);
    load();
    refreshProvider();
    return `Model aktif sekarang ${model}.`;
  });
  const resetActive = () => act("reset", async () => {
    const result = await api.ai.resetActive();
    load();
    refreshProvider();
    return result.active_model ? `Kembali ke model dari .env: ${result.active_model}.` : "Pilihan dihapus. Belum ada model aktif.";
  });
  const unload = (model: string) => act(`unload:${model}`, async () => {
    await api.ai.unload(model);
    load();
    return `${model} dilepas dari memori. File model tetap ada.`;
  });
  const startEval = (model: string) => act(`eval:${model}`, async () => {
    await api.ai.startEvaluation(model);
    return `Uji ${model} dimulai — lihat progresnya di bawah atau di Task Manager.`;
  });
  const toggleDetails = (model: string) => {
    if (details[model]) {
      setDetails((prev) => {
        const next = { ...prev };
        delete next[model];
        return next;
      });
      return;
    }
    api.ai.model(model).then((d) => setDetails((prev) => ({ ...prev, [model]: d })))
      .catch((err) => setDetails((prev) => ({ ...prev, [model]: errorText(err, "Detail tidak dapat dimuat.") })));
  };

  return (
    <section className="page" data-testid="ai-local-page">
      <p className="muted"><Link to="/settings">Settings</Link> › AI Lokal</p>
      <h1>AI Lokal</h1>
      <p className="muted">
        Semua angka di halaman ini dibaca langsung dari Ollama. <strong>ZOI tidak pernah mengunduh atau menghapus
        model</strong> — pemasangan model dilakukan sendiri lewat perintah <code>ollama</code>.
      </p>
      {loadError && <p className="notice bad" role="alert">{loadError}</p>}
      {notice && <p className={`notice ${notice.kind}`} role="status" data-testid="ai-notice">{notice.text}</p>}
      {!status ? (!loadError && <p className="muted">Memuat…</p>) : (
        <>
          <StatusSection status={status} busy={busy} onTest={testConnection} onReset={resetActive} />
          {status.reachable && (
            <>
              <h2>Model terpasang</h2>
              {status.installed.length === 0
                ? <p className="muted">Belum ada model di Ollama ini. Lihat katalog di bawah untuk perintah pemasangan.</p>
                : (
                  <ul className="model-list" data-testid="installed-models">
                    {status.installed.map((m) => (
                      <InstalledRow key={m.name} model={m} active={m.name === status.active_model} busy={busy}
                        evalRunning={!!runningEval} details={details[m.name]} onActive={makeActive}
                        onDetails={toggleDetails} onEval={startEval} />
                    ))}
                  </ul>
                )}
              <h2>Sedang dimuat di memori</h2>
              {status.running.length === 0 ? <p className="muted">Tidak ada model yang sedang dimuat.</p> : (
                <ul className="model-list" data-testid="running-models">
                  {status.running.map((r) => (
                    <li key={r.name} className="model-item">
                      <div className="model-head"><strong>{r.name}</strong></div>
                      <dl className="kv">
                        <dt>Memori</dt><dd>{formatBytes(r.size_bytes)} (VRAM {formatBytes(r.vram_bytes)})</dd>
                        <dt>Konteks</dt><dd>{r.context_tokens ? `${r.context_tokens.toLocaleString("id-ID")} token` : "tidak dilaporkan"}</dd>
                        <dt>Dilepas otomatis</dt><dd>{formatTime(r.expires_at)}</dd>
                      </dl>
                      <div className="row">
                        <button type="button" disabled={busy !== null} onClick={() => unload(r.name)}>
                          Lepaskan dari memori
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
          {!status.is_mock && status.provider === "ollama" && !status.reachable && <InstallGuide />}
          <CatalogSection status={status} />
          {!status.is_mock && status.provider === "ollama" && (
            <EvaluationSection evaluations={evaluations} runningTask={runningEval}
              onUpdated={(updated) => setEvaluations((list) => list.map((e) => (e.id === updated.id ? { ...e, ...updated } : e)))} />
          )}
        </>
      )}
    </section>
  );
}

function StatusSection({ status, busy, onTest, onReset }: {
  status: AiStatus; busy: string | null; onTest(): void; onReset(): void;
}) {
  const tone = status.is_mock ? "warn" : status.ready ? "ok" : "bad";
  return (
    <>
      <p className={`notice ${tone}`} data-testid="ai-status-detail">{status.detail}</p>
      <dl className="kv" data-testid="ai-status">
        <dt>Penyedia</dt><dd>{status.provider}{status.is_mock ? " (tiruan)" : ""}</dd>
        {status.url && <><dt>Alamat Ollama</dt><dd>{status.url} · {status.location}</dd></>}
        {status.version && <><dt>Versi Ollama</dt><dd>{status.version}</dd></>}
        <dt>Model aktif</dt>
        <dd data-testid="active-model">
          {status.active_model ?? "—"} <span className="muted">({SOURCE_LABEL[status.active_source]})</span>
        </dd>
      </dl>
      {status.provider === "ollama" && (
        <div className="row">
          <button type="button" onClick={onTest} disabled={busy !== null}>Uji koneksi</button>
          {status.active_source === "ui" && (
            <button type="button" onClick={onReset} disabled={busy !== null}>
              {status.env_model ? `Kembali ke model .env (${status.env_model})` : "Hapus pilihan model"}
            </button>
          )}
        </div>
      )}
    </>
  );
}

function InstalledRow({ model, active, busy, evalRunning, details, onActive, onDetails, onEval }: {
  model: InstalledModel; active: boolean; busy: string | null; evalRunning: boolean;
  details: ModelDetails | string | undefined; onActive(m: string): void; onDetails(m: string): void; onEval(m: string): void;
}) {
  return (
    <li className="model-item" data-testid="installed-model">
      <div className="model-head">
        <strong>{model.name}</strong>
        {active && <span className="badge ok" data-testid="active-badge">aktif</span>}
        {model.is_cloud && <span className="badge bad">cloud — tidak diizinkan</span>}
      </div>
      <p className="muted model-meta">
        {[formatBytes(model.size_bytes), model.parameter_size, model.quantization, model.family]
          .filter((v) => v && v !== "—").join(" · ") || "Ukuran & detail tidak dilaporkan"}
      </p>
      {!model.is_cloud && (
        <div className="row">
          <button type="button" className="primary" disabled={active || busy !== null} onClick={() => onActive(model.name)}>
            {active ? "Model aktif" : "Jadikan model aktif"}
          </button>
          <button type="button" onClick={() => onDetails(model.name)} aria-expanded={!!details}>
            {details ? "Tutup detail" : "Detail"}
          </button>
          <button type="button" disabled={evalRunning || busy !== null} onClick={() => onEval(model.name)}>
            Uji model
          </button>
        </div>
      )}
      {typeof details === "string" && <p className="notice bad">{details}</p>}
      {details && typeof details !== "string" && (
        <dl className="kv" data-testid="model-details">
          <dt>Kemampuan</dt><dd>{details.capabilities.join(", ") || "tidak dilaporkan"}</dd>
          <dt>Konteks maksimum</dt>
          <dd>{details.context_tokens ? `${details.context_tokens.toLocaleString("id-ID")} token` : "tidak dilaporkan"}</dd>
          <dt>Arsitektur</dt><dd>{details.architecture ?? "tidak dilaporkan"}</dd>
          <dt>Lisensi</dt><dd>{details.license_line ?? "tidak dilaporkan — periksa sebelum dipakai"}</dd>
        </dl>
      )}
    </li>
  );
}

function InstallGuide() {
  return (
    <div className="notice warn" data-testid="install-guide">
      <strong>Ollama belum terhubung.</strong>
      <ol>
        <li>Unduh Ollama untuk Windows dari situs resmi <code>ollama.com/download</code> (gratis, MIT).</li>
        <li>
          Agar drive C: tidak penuh, simpan model di drive lain: atur environment variable Windows
          <code> OLLAMA_MODELS</code> ke folder di drive lain (mis. <code>D:\ollama\models</code>), lalu mulai ulang Ollama.
        </li>
        <li>Pasang satu model dari katalog di bawah dengan perintah <code>ollama pull</code> di Command Prompt.</li>
        <li>Pastikan Ollama berjalan, lalu muat ulang halaman ini.</li>
      </ol>
      <p className="muted">Ollama di komputer lain di jaringan rumah? Isi <code>ZOI_OLLAMA_URL</code> dan tambahkan alamatnya ke
        <code> ZOI_EXTRA_ALLOWED_HOSTS</code> di file .env, lalu restart ZOI.</p>
    </div>
  );
}

function CatalogSection({ status }: { status: AiStatus }) {
  const [copied, setCopied] = useState<string | null>(null);
  const installed = new Set(status.installed.map((m) => m.name));
  async function copy(command: string) {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(command);
    } catch {
      setCopied(null);
    }
  }
  return (
    <>
      <h2>Katalog model kandidat</h2>
      <p className="muted">Ukuran adalah perkiraan dari {status.catalog.source.replace(/\.$/, "")}. Pasang sendiri lewat
        perintah; ZOI tidak mengunduh apa pun.</p>
      <ul className="model-list" data-testid="catalog">
        {status.catalog.models.map((m) => {
          const command = `ollama pull ${m.tag}`;
          return (
            <li key={m.tag} className="model-item">
              <div className="model-head">
                <strong>{m.tag}</strong>
                <span className="badge">{m.license}</span>
                {installed.has(m.tag) && <span className="badge ok">terpasang</span>}
              </div>
              <p className="muted model-meta">{m.family} · unduhan ±{m.download} · konteks {m.context}</p>
              <p className="model-fit">{m.fit}</p>
              <div className="row command-row">
                <code className="command">{command}</code>
                <button type="button" onClick={() => copy(command)}>{copied === command ? "Tersalin" : "Salin perintah"}</button>
              </div>
            </li>
          );
        })}
      </ul>
      {status.catalog.not_default.map((n) => <p key={n.family} className="muted">⚠️ {n.family}: {n.reason}</p>)}
    </>
  );
}

function EvaluationSection({ evaluations, runningTask, onUpdated }: {
  evaluations: EvaluationInfo[]; runningTask: { name: string; progress: number; message: string } | undefined;
  onUpdated(e: EvaluationInfo): void;
}) {
  const [open, setOpen] = useState<EvaluationInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function show(id: string) {
    if (open?.id === id) { setOpen(null); return; }
    try { setOpen(await api.ai.evaluation(id)); } catch (err) { setError(errorText(err, "Hasil uji tidak dapat dimuat.")); }
  }
  async function rate(promptId: string, rating: "up" | "down") {
    if (!open) return;
    const next = open.rating_by_prompt?.[promptId] === rating ? null : rating;
    try {
      const updated = await api.ai.rate(open.id, promptId, next);
      setOpen(updated);
      onUpdated(updated);
    } catch (err) {
      setError(errorText(err, "Penilaian gagal disimpan."));
    }
  }

  return (
    <>
      <h2>Uji kecocokan model</h2>
      <p className="muted">
        20 prompt Bahasa Indonesia yang sama untuk setiap model: 10 percakapan, 5 JSON, 5 pemanggilan tool. Kecepatan,
        JSON, dan tool diukur otomatis. Kualitas jawaban percakapan dinilai olehmu (👍/👎) — ZOI tidak menilainya sendiri.
        Di komputer lambat satu uji bisa memakan waktu lama.
      </p>
      {runningTask && (
        <div className="notice warn" data-testid="eval-running">
          <strong>{runningTask.name}</strong> — {runningTask.message}
          <progress max={100} value={runningTask.progress} aria-label="Progress uji model" />
        </div>
      )}
      {error && <p className="notice bad" role="alert">{error}</p>}
      {evaluations.length === 0 ? <p className="muted">Belum ada hasil uji. Pilih "Uji model" pada model terpasang.</p> : (
        <ul className="model-list" data-testid="evaluations">
          {evaluations.map((e) => (
            <li key={e.id} className="model-item">
              <div className="model-head">
                <strong>{e.model}</strong>
                <span className="muted">{e.machine} · {formatTime(e.finished_at)}</span>
              </div>
              <p className="model-meta">
                JSON {e.summary.json.passed}/{e.summary.json.total} · Tool {e.summary.tool.passed}/{e.summary.tool.total}
                {" · "}Token pertama {e.summary.median_first_token_s ?? "—"} dtk
                {" · "}{e.summary.median_tokens_per_s ?? "—"} token/dtk
                {" · "}Penilaianmu 👍 {e.ratings.up} 👎 {e.ratings.down}
              </p>
              <div className="row">
                <button type="button" onClick={() => show(e.id)}>{open?.id === e.id ? "Tutup" : "Lihat jawaban"}</button>
              </div>
              {open?.id === e.id && open.results && (
                <ol className="eval-results">
                  {open.results.map((r) => (
                    <li key={r.id} className="eval-result">
                      <p><strong>{r.id}</strong> <span className="badge">{r.category}</span> {r.prompt}</p>
                      {r.error ? <p className="msg-error">{r.error}</p> : r.response && <p className="msg-body">{r.response}</p>}
                      <p className="muted">
                        {r.passed === true ? "✓ " : r.passed === false ? "✗ " : ""}{r.detail}
                        {r.first_token_s != null && ` · token pertama ${r.first_token_s} dtk`}
                        {r.tokens_per_s != null && ` · ${r.tokens_per_s} token/dtk`}
                      </p>
                      {r.category === "chat" && !r.error && (
                        <div className="row">
                          {(["up", "down"] as const).map((v) => (
                            <button key={v} type="button" aria-pressed={open.rating_by_prompt?.[r.id] === v}
                              aria-label={`${v === "up" ? "Bagus" : "Kurang"}: ${r.id}`} onClick={() => rate(r.id, v)}>
                              {v === "up" ? "👍" : "👎"}
                            </button>
                          ))}
                        </div>
                      )}
                    </li>
                  ))}
                </ol>
              )}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
