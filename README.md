# ZOI — Command Center (YouTube Intelligence)

Platform web lokal dengan avatar ZOI sebagai pusat kendali ekosistem YouTube.
**ZERO PAID API · ZERO SUBSCRIPTION · LOCAL FIRST.** Lisensi: MIT.

> Status: **Phase 6B — data publik YouTube & draf konten** (di atas Phase 1–6A). Lihat tabel "Yang sudah berfungsi" di bawah. Fitur yang belum dibangun
> ditampilkan sebagai "Belum tersedia — Phase N", tanpa data contoh.

## Arsitektur singkat

| Bagian | Lokasi | Catatan |
|---|---|---|
| Frontend | `frontend/apps/web` | React + TypeScript + Vite. Di mode local disajikan backend sebagai file statis |
| Avatar | `frontend/packages/avatar` | Paket terpisah. 2D (SVG) dan 3D (talking-avatar + three.js, aset lokal); renderer dipilih otomatis — lihat ADR 0005 |
| Backend | `backend/app` | FastAPI, satu proses, bind `127.0.0.1` saja |
| Database | `backend/app/db` | SQLite satu file di `ZOI_DATA_DIR`, migrasi Alembic, ekspor/impor ZIP berverifikasi |
| Penyedia AI | `backend/app/providers` | `mock` (development, selalu berlabel MOCK) · `ollama` (local) · `none` |
| Integrasi | `backend/app/integrations` | Adapter ZOI AI CLIPPER & Blueprint Studio — **read-only**, aplikasi asli tidak diubah |

## Dua mode

| | `ZOI_MODE=development` | `ZOI_MODE=local` |
|---|---|---|
| Penyedia AI | Mock (jawaban berlabel **MOCK**, tidak pernah membuat statistik) | Ollama lokal; **mock ditolak** |
| Alamat | Vite `http://127.0.0.1:5173` → backend `:8000` | Satu alamat: `http://127.0.0.1` (port 80) |
| Banner | Pita kuning "DEVELOPMENT MODE" | Tidak ada |

Semua konfigurasi lewat environment variable / file `.env` — lihat `.env.development.example` dan
`.env.local.example`. Nama variabel yang salah ketik ditolak saat start.

## Menjalankan

**Development** (workspace pengembangan, butuh Python 3.12+ dan Node 22.12+):

```bash
cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && cd ..
cd frontend && npm ci && cd ..
scripts/dev.sh            # buka http://127.0.0.1:5173
```

**Local server Windows**: pakai paket rilis (frontend sudah di-build, tanpa Node.js) dan ikuti
[`docs/MIGRATION_TO_LOCAL_SERVER.md`](docs/MIGRATION_TO_LOCAL_SERVER.md).

## Alat baris perintah

```bash
cd backend
python -m app.cli doctor                         # cek Python, disk, port, frontend, Ollama, path, portabilitas
python -m app.cli data export --exclude-mock     # satu file ZIP berisi semua data + checksum
python -m app.cli data import <file.zip>         # pulihkan (ZOI harus berhenti; data lama di-backup dulu)
python -m app.cli db upgrade | db status | backup
```

## Yang sudah berfungsi (Phase 1–6B)

| Fitur | Status |
|---|---|
| Layout command center 5 zona, 16 menu, responsif 375–1440 px | ✅ |
| Avatar 2D mengikuti 12 status nyata dari backend | ✅ |
| Chat minimal (Mock di development, Ollama di local) dengan streaming | ✅ |
| Task Manager: progress langsung, riwayat, pembatalan; tugas nyata "Pemeriksaan sistem" | ✅ |
| Status sistem, penyedia AI, dan deteksi CLIPPER/Blueprint (read-only) | ✅ |
| Cost Guard: koneksi keluar hanya ke allowlist; layanan AI berbayar diblokir & dicatat | ✅ |
| Ekspor/impor data portabel + backup otomatis sebelum migrasi | ✅ |
| Avatar 3D (wajah Rocketbox): lip-sync dari audio, kedip, alis; fallback 2D otomatis (WebGL 2, uji FPS, `ZOI_AVATAR_MODE=2d`) | ✅ |
| Settings: mode avatar, karakter, uji ulang perangkat, uji lip-sync dari file lokal | ✅ |
| Gerak kepala / arah pandang / ekspresi avatar | tidak didukung paket (ADR 0005) |
| Settings › AI Lokal: status & versi Ollama, model terpasang (ukuran, kemampuan, konteks, lisensi), model di memori, pilih model aktif, lepaskan dari memori | ✅ (diuji dengan Ollama tiruan) |
| ZOI **tidak pernah** mengunduh/menghapus model — endpoint `pull/delete/create/push/copy` diblokir di klien; katalog hanya memberi perintah salin | ✅ |
| Chat: riwayat dipotong sesuai konteks model, proses berpikir terpisah (dilipat), tombol Berhenti | ✅ |
| Keluaran JSON tervalidasi (`chat_json`) + 1× percobaan ulang — fondasi agent | ✅ |
| Uji kecocokan model: 20 prompt Bahasa Indonesia, angka terukur + penilaian 👍/👎 pengguna (`zoi-cli ai eval`) | ✅ (belum dijalankan dengan model sungguhan) |
| Bicara ke ZOI: tekan 🎙 → faster-whisper lokal → teks masuk kotak pesan (rekaman tidak disimpan, tanpa cloud) | ✅ (diuji dengan tiruan; model asli belum) |
| ZOI membacakan jawaban per kalimat: Piper (program terpisah, lip-sync avatar 3D) atau suara lokal Windows; tombol Berhenti | ✅ (Piper diuji dengan tiruan) |
| Settings › Suara: status, bahasa, kirim otomatis, mesin suara, kecepatan, catatan lisensi Piper, cara memasang | ✅ |
| Agen atas permintaan (tombol **Rencanakan** / `/agen`): rencana ditampilkan dulu, langkah ubah-data minta izin, hasil per langkah, ringkasan dengan cek angka | ✅ (diuji dengan Mock & Ollama tiruan) |
| 10 tool nyata (memori, status sistem/AI/aplikasi, tugas, waktu); **tidak ada tool publikasi** | ✅ |
| Halaman **Memory**: tambah, cari (FTS5), ubah, hapus, hapus semua dengan konfirmasi; izin tool; log izin | ✅ |
| Settings › YouTube: hubungkan channel lewat OAuth resmi (PKCE, hanya-baca), token di Windows Credential Manager, kuota, **Putuskan & hapus data** | ✅ (diuji dengan Google tiruan; koneksi asli belum) |
| Channel Analytics: statistik channel, laporan 28 hari & harian, video terbaru, riwayat harian — angka persis dari YouTube dengan sumber & waktu ambil | ✅ (diuji dengan Google tiruan) |
| Monetization: syarat resmi YPP berdampingan dengan angka channel, **tanpa** persentase/perkiraan buatan ZOI | ✅ |
| Tool agen `youtube_channel_saya`, `youtube_video_saya` (selalu minta izin), `youtube_kuota` | ✅ |
| Competitor Intelligence: channel pantauan (maks. 20), data publik apa adanya, **dihapus otomatis setelah 30 hari**, tanpa skor | ✅ (diuji dengan Google tiruan) |
| Viral Video Hunter: Trending resmi Indonesia per kategori + pencarian (ember kuota sendiri), urutan dari YouTube | ✅ (diuji dengan Google tiruan) |
| Trend Detector: AI lokal merangkum tema dari **judul** saja; berlabel "interpretasi AI, bukan statistik"; contoh karangan dibuang | ✅ (diuji dengan Mock & Ollama tiruan) |
| Content Ideas dan Script & Storyboard: draf AI lokal berlabel penyedia/model, unduh Markdown; **tidak ada publikasi** | ✅ (diuji dengan Mock & Ollama tiruan) |
| Performance: laporan per video channel sendiri dari YouTube Analytics | ✅ (diuji dengan Google tiruan) |
| Skor viral, riwayat kompetitor, "waktu upload terbaik" | sengaja tidak dibuat (ADR 0010) |
| CLIPPER/Blueprint penuh, automation | Phase 7–8 |

## Pengujian

```bash
cd backend && .venv/bin/python -m pytest          # backend
cd frontend && npm run lint && npm run typecheck && npm test
cd frontend && E2E_CHROME=/path/ke/chrome npx playwright test   # E2E development + local
backend/.venv/bin/python scripts/check_licenses.py              # lisensi semua dependensi
```

## Dokumen

- `docs/audit/` — audit Phase 0 dan rencana Phase 1
- `docs/adr/` — keputusan arsitektur (YouTube: `0009-youtube-akun-sendiri.md`, `0010-data-publik-dan-draf-konten.md`)
- `THIRD_PARTY_NOTICES.md` — lisensi dependensi (dibuat otomatis)
