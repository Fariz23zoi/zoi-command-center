import { api, type SystemStatus } from "@zoi/api-client";
import { useEffect, useState } from "react";

import { formatBytes, formatTime } from "../lib/format";
import { useApp } from "../stores/appStore";

export function OverviewPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const provider = useApp((s) => s.provider);
  const adapters = useApp((s) => s.adapters);
  const config = useApp((s) => s.config);

  useEffect(() => {
    api.systemStatus().then(setStatus).catch(() => setError("Status sistem tidak dapat dibaca dari backend."));
  }, []);

  return (
    <section className="page">
      <h1>Overview</h1>
      {config?.warnings.map((w) => <p key={w} className="notice warn">{w}</p>)}

      <h2>Sistem</h2>
      {error && <p className="notice bad">{error}</p>}
      {!status && !error && <p className="muted">Membaca status sistem…</p>}
      {status && (
        <>
          <dl className="kv">
            <dt>Sistem operasi</dt><dd>{status.os.system} {status.os.release}</dd>
            <dt>Python</dt><dd>{status.python.version}</dd>
            <dt>CPU</dt><dd>{status.resources.cpu.logical_cores ?? "—"} thread</dd>
            <dt>RAM tersedia</dt>
            <dd>{formatBytes(status.resources.memory.available_bytes)} dari {formatBytes(status.resources.memory.total_bytes)}</dd>
            <dt>Disk kosong</dt><dd>{formatBytes(status.resources.disk.free_bytes)}</dd>
          </dl>
          <ul className="tool-list">
            {Object.values(status.tools).map((tool) => (
              <li key={tool.name} className={tool.found ? "ok" : "missing"}>
                <strong>{tool.name}</strong> {tool.found ? tool.version ?? "ditemukan" : "tidak ditemukan"}
              </li>
            ))}
          </ul>
          <p className="source">Sumber: {status.source} · {formatTime(status.checked_at)}</p>
        </>
      )}

      <h2>Penyedia AI</h2>
      {provider ? (
        <p className={`notice ${provider.available ? (provider.is_mock ? "warn" : "ok") : "bad"}`}>
          <strong>{provider.name}</strong> — {provider.detail}
        </p>
      ) : <p className="muted">Memeriksa…</p>}

      <h2>Aplikasi terintegrasi</h2>
      <ul className="adapter-list">
        {adapters.map((a) => (
          <li key={a.name}>
            <strong>{a.name === "zoi_ai_clipper" ? "ZOI AI CLIPPER" : "Blueprint Studio"}</strong>{" "}
            {a.found ? "ditemukan (read-only)" : a.configured ? "tidak ditemukan" : "belum dikonfigurasi"}
          </li>
        ))}
      </ul>
    </section>
  );
}
