import { api, type TaskInfo } from "@zoi/api-client";

/** Tunggu tugas latar selesai (polling ringan — cocok untuk laptop lemah). */
export async function waitTask(id: string, onUpdate?: (t: TaskInfo) => void, signal?: { stop: boolean }): Promise<TaskInfo> {
  for (;;) {
    const task = await api.task(id);
    onUpdate?.(task);
    if (task.status === "COMPLETED" || task.status === "FAILED" || task.status === "CANCELLED") return task;
    if (signal?.stop) return task;
    await new Promise((r) => setTimeout(r, 1500));
  }
}

export function download(blob: Blob, filename: string): void {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename.replace(/[\\/:*?"<>|]+/g, "-").slice(0, 120) || "unduhan.txt";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 3000);
}

export const timeText = (t: number) => new Date(t * 1000).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" });
