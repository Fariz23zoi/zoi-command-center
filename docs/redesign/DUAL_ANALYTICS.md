# Dual YouTube Analytics — audit & implementasi (16 Nov 2026)

## Audit integrasi (sebelum)
| Kebutuhan | Sudah ada | Ditambah |
|---|---|---|
| OAuth 2.0 channel sendiri, disconnect/reconnect | ✅ PKCE, token di Credential Manager/terenkripsi, revoke di Google | — |
| Subscriber, views, watch time, per video | ✅ Analytics API (28 hari, harian, 365 hari, per video) | Pembanding 28 hari sebelumnya, sumber traffic, perangkat |
| Audience retention | ⚠️ hanya `averageViewPercentage` | Kurva retensi per video (`elapsedVideoTimeRatio`), on-demand, cache 12 jam |
| Kompetitor via Data API v3 tanpa login | ✅ ID / @handle / URL, maks 20 | Cari berdasarkan **nama** (`search.list type=channel`, 100 unit) |
| Video terbaru kompetitor | ✅ 10 | 25 (playlistItems + videos = 2 unit) |
| Histori kompetitor | ❌ cache ditimpa | Snapshot harian saat refresh, label "Histori dikumpulkan ZOI" |
| Caching kuota | ⚠️ kuota dijaga, tanpa TTL | Refresh kompetitor < 1 jam = cache (`?force=true` untuk paksa) |
| Multi-pengguna | ZOI = **satu pemilik** (mode local; akses HP dibatasi `ZOI_REMOTE_USER`; mode online = login pemilik) | Tidak diubah — data milik satu pemilik |

## Aturan data (kebijakan YouTube API Services)
- **Aktual**: angka dari YouTube saat diambil (badge hijau).
- **Histori dikumpulkan ZOI**: titik snapshot yang benar-benar diambil ZOI. Channel lain = data tidak berizin → **dihapus setelah 30 hari**; channel sendiri = data berizin → disimpan selama izin aktif & dicek ulang tiap 30 hari.
- **Estimasi AI**: belum dipakai di dashboard; bila ditambah wajib berlabel kuning.
- Tidak ada skor/metrik turunan buatan ZOI (Upload Frequency ditampilkan sebagai titik tanggal publish, bukan skor).

## API baru
- `POST /api/youtube/public/channels/search {query}`
- `POST /api/youtube/public/competitors/{id}/refresh?force=true`
- `POST /api/youtube/videos/{video_id}/retention`
