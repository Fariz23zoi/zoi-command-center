import { type AgentRunInfo, api, ApiError, type ToolPermission } from "@zoi/api-client";
import { useState } from "react";

import { useApp } from "../stores/appStore";

const STATUS_LABEL: Record<AgentRunInfo["status"], string> = {
  planning: "Menyusun rencana…",
  invalid: "Rencana tidak valid",
  planned: "Rencana siap — menunggu persetujuanmu",
  rejected: "Rencana dibatalkan",
  running: "Menjalankan langkah…",
  waiting_approval: "Menunggu izinmu",
  completed: "Selesai",
  failed: "Gagal",
  stopped: "Dihentikan — izin tidak diberikan",
  cancelled: "Dibatalkan",
};

const PERMISSION_LABEL: Record<ToolPermission, string> = {
  read: "baca",
  write_local: "ubah data — perlu izin",
  external: "pakai layanan luar — selalu perlu izin",
};

function short(value: unknown): string {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return text.length > 400 ? `${text.slice(0, 400)}…` : text;
}

/** Kartu satu permintaan agen di dalam chat: rencana → persetujuan → langkah → izin → hasil. */
export function AgentRunCard({ run }: { run: AgentRunInfo }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = run.approvals.find((a) => a.status === "pending");
  const steps = run.plan?.langkah ?? [];
  const finished = ["completed", "failed", "stopped", "cancelled"].includes(run.status);

  async function act(action: () => Promise<AgentRunInfo>) {
    setBusy(true);
    setError(null);
    try {
      useApp.getState().setAgentRuns([await action()]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Permintaan gagal.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={`agent-card agent-${run.status}`} data-testid="agent-card" data-status={run.status}>
      <div className="agent-head">
        <strong>Agen</strong>
        {run.is_mock && <span className="badge mock">MOCK</span>}
        <span className="agent-status" data-testid="agent-status">{STATUS_LABEL[run.status]}</span>
      </div>
      {run.plan && <p className="agent-goal">{run.plan.tujuan}</p>}

      {steps.length > 0 && (
        <ol className="agent-steps">
          {steps.map((step, index) => {
            const result = run.results.find((r) => r.index === index);
            const waiting = pending?.step_index === index;
            return (
              <li key={index} className={`agent-step ${result ? `step-${result.status}` : waiting ? "step-waiting" : ""}`}
                data-testid="agent-step">
                <div className="agent-step-head">
                  <code>{step.tool}</code>
                  {step.permission && <span className={`badge perm-${step.permission}`}>{PERMISSION_LABEL[step.permission]}</span>}
                  {result && <span className="badge">{result.status === "ok" ? "✓ berhasil" : result.status === "rejected" ? "tidak dijalankan" : "✗ gagal"}</span>}
                </div>
                {step.alasan && <p className="muted">{step.alasan}</p>}
                {Object.keys(step.argumen).length > 0 && <p className="agent-args"><code>{short(step.argumen)}</code></p>}
                {result?.error && <p className="msg-error">{result.error}</p>}
                {result?.status === "ok" && result.output != null && (
                  <details className="agent-output">
                    <summary>Hasil</summary>
                    <pre>{short(result.output)}</pre>
                  </details>
                )}
              </li>
            );
          })}
        </ol>
      )}

      {run.errors.length > 0 && (
        <ul className="agent-errors" role="alert">{run.errors.map((e) => <li key={e}>{e}</li>)}</ul>
      )}

      {run.status === "planned" && (
        <div className="row">
          <button type="button" className="primary" disabled={busy} onClick={() => act(() => api.agent.approve(run.id))}>
            Jalankan rencana
          </button>
          <button type="button" disabled={busy} onClick={() => act(() => api.agent.reject(run.id))}>Batal</button>
        </div>
      )}

      {pending && (
        <div className="notice warn agent-approval" data-testid="agent-approval">
          <strong>Izinkan langkah ini?</strong>
          <p><code>{pending.tool}</code> {Object.keys(pending.args).length > 0 && <code>{short(pending.args)}</code>}</p>
          <div className="row">
            <button type="button" className="primary" disabled={busy}
              onClick={() => act(() => api.agent.decide(pending.id, "approve"))}>Setujui</button>
            <button type="button" disabled={busy} onClick={() => act(() => api.agent.decide(pending.id, "reject"))}>
              Tolak
            </button>
          </div>
        </div>
      )}

      {(run.status === "running" || run.status === "waiting_approval") && (
        <div className="row">
          <button type="button" disabled={busy} onClick={() => act(() => api.agent.cancel(run.id))}>Batalkan permintaan</button>
        </div>
      )}

      {finished && run.task_id && <p className="muted">Ringkasan ada di pesan ZOI di bawah. Riwayat lengkap di Task Manager.</p>}
      {error && <p className="msg-error" role="alert">{error}</p>}
    </div>
  );
}
