import { api, ApiError, type YouTubeData } from "@zoi/api-client";
import { useCallback, useEffect, useState } from "react";

import { useApp } from "../stores/appStore";

const NUMBER = new Intl.NumberFormat("id-ID");

/** Menampilkan angka persis dari YouTube (hanya diberi pemisah ribuan). Kosong → "—", bukan nol. */
export function exact(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  return typeof value === "number" ? NUMBER.format(value) : value;
}

export function errorText(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

/** Nama kolom laporan YouTube Analytics → label Indonesia. Nilainya tidak diubah. */
export const METRIC_LABEL: Record<string, string> = {
  day: "Tanggal",
  views: "Tayangan",
  estimatedMinutesWatched: "Menit ditonton (perkiraan YouTube)",
  averageViewDuration: "Rata-rata durasi tonton (detik)",
  subscribersGained: "Subscriber bertambah",
  subscribersLost: "Subscriber berkurang",
  averageViewPercentage: "Rata-rata persentase ditonton (hitungan YouTube)",
};

/** Data YouTube yang tersimpan di komputer ini; dimuat ulang saat backend mengabarkan perubahan. */
export function useYouTubeData() {
  const revision = useApp((s) => s.youtubeRevision);
  const [data, setData] = useState<YouTubeData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.youtube.data().then((d) => { setData(d); setError(null); })
      .catch((err) => setError(errorText(err, "Data YouTube tidak dapat dimuat.")));
  }, [revision]);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setData(await api.youtube.refresh("all"));
    } catch (err) {
      setError(errorText(err, "Gagal mengambil data dari YouTube."));
    } finally {
      setBusy(false);
    }
  }, []);

  return { data, error, busy, refresh };
}
