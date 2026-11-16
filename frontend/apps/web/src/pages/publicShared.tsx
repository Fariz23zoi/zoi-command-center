import type { PublicInfo, PublicVideo, TaskInfo } from "@zoi/api-client";
import { useState } from "react";
import { Link } from "react-router-dom";

import { formatTime } from "../lib/format";
import { exact } from "../lib/youtube";
import { useApp } from "../stores/appStore";

/** Keterangan tetap untuk semua halaman data publik: sumber, aturan 30 hari, dan status koneksi. */
export function PublicNote({ info }: { info: PublicInfo }) {
  return (
    <>
      {info.test_endpoint && (
        <p className="notice warn" data-testid="youtube-test-banner">
          ENDPOINT UJI — data di halaman ini berasal dari server tiruan, bukan YouTube.
        </p>
      )}
      {!info.connected && (
        <p className="notice warn" data-testid="public-not-connected">
          Channel YouTube belum terhubung, jadi ZOI belum bisa mengambil data.{" "}
          <Link to="/settings/youtube">Hubungkan di Settings › YouTube</Link>.
        </p>
      )}
      <p className="muted" data-testid="public-policy">
        Data publik diambil lewat API resmi YouTube dan ditampilkan apa adanya. Disimpan paling lama{" "}
        {info.retention_days} hari lalu dihapus otomatis (aturan YouTube). ZOI tidak membuat skor atau peringkat sendiri.
      </p>
    </>
  );
}

export function Stamp({ info, fetchedAt, expiresAt }: { info: PublicInfo; fetchedAt: string; expiresAt: string }) {
  return (
    <p className="source" data-testid="youtube-source">
      Sumber: {info.source} · diambil {formatTime(fetchedAt)} · dihapus otomatis {formatTime(expiresAt)}
    </p>
  );
}

/** Daftar video dalam urutan yang dikirim YouTube. Angka kosong tampil "—", tidak pernah dikarang. */
export function VideoTable({ videos, testId, showChannel = true }: {
  videos: PublicVideo[]; testId: string; showChannel?: boolean;
}) {
  if (videos.length === 0) return <p className="muted">YouTube tidak mengirim video untuk daftar ini.</p>;
  return (
    <div className="table-wrap">
      <table className="data-table" data-testid={testId}>
        <thead><tr>
          <th scope="col">Judul</th>{showChannel && <th scope="col">Channel</th>}<th scope="col">Terbit</th>
          <th scope="col">Tayangan</th><th scope="col">Suka</th><th scope="col">Komentar</th>
        </tr></thead>
        <tbody>
          {videos.map((v, i) => (
            <tr key={v.id ?? i}>
              <td>{v.id
                ? <a href={`https://www.youtube.com/watch?v=${encodeURIComponent(v.id)}`} target="_blank"
                    rel="noopener noreferrer">{v.title}</a>
                : v.title}</td>
              {showChannel && <td>{v.channel_title || "—"}</td>}
              <td>{formatTime(v.published_at)}</td>
              <td>{exact(v.view_count)}</td><td>{exact(v.like_count)}</td><td>{exact(v.comment_count)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Mengikuti satu tugas latar (AI lokal bisa butuh beberapa menit) lewat event Task Manager. */
export function useTaskWatch() {
  const [started, setStarted] = useState<TaskInfo | null>(null);
  const live = useApp((s) => (started ? s.tasks.find((t) => t.id === started.id) : undefined));
  const task = live ?? started;
  const running = task?.status === "QUEUED" || task?.status === "RUNNING";
  return { task, running, watch: setStarted };
}

export function TaskNotice({ task }: { task: TaskInfo | null | undefined }) {
  if (!task) return null;
  if (task.status === "QUEUED" || task.status === "RUNNING") {
    return (
      <p className="notice warn" role="status" data-testid="content-task">
        {task.message || "Menunggu giliran…"} AI lokal bisa butuh beberapa menit di laptop ini. Pantau di{" "}
        <Link to="/tasks">Task Manager</Link>.
      </p>
    );
  }
  if (task.status === "FAILED") {
    return <p className="notice bad" role="alert" data-testid="content-task">Gagal: {task.error ?? "tanpa keterangan"}</p>;
  }
  if (task.status === "CANCELLED") return <p className="notice warn" data-testid="content-task">Dibatalkan.</p>;
  return <p className="notice ok" role="status" data-testid="content-task">Selesai.</p>;
}

export function AiStamp({ item }: { item: { is_mock: boolean; provider: string; model: string | null } }) {
  return (
    <p className="source" data-testid="ai-stamp">
      {item.is_mock
        ? "MOCK — teks tiruan untuk menguji tampilan, bukan hasil AI."
        : `Draf AI lokal (${item.provider}${item.model ? ` · ${item.model}` : ""}) — periksa sebelum dipakai.`}
    </p>
  );
}
