# ZOI — Command Center (YouTube Intelligence)

Platform web dengan avatar ZOI sebagai pusat kendali ekosistem YouTube.
**ZERO PAID API · ZERO SUBSCRIPTION.** Lisensi: MIT. Versi **1.1.1**. Online = laptop + Tailscale (lihat `docs/AKSES_HP.md`).

> Bentuk akhir: **ZOI online** (Render + Neon, gratis) untuk dibuka dari HP — chat, analitik, kompetitor, tren,
> ide, naskah, otomatisasi — dan **ZOI laptop** (mode local) untuk produksi konten: narasi, Blueprint Studio,
> render. CLIPPER **ditunda** (yt-dlp bertentangan dengan ketentuan YouTube). Fitur yang tidak bisa berjalan
> tanpa layanan berbayar ditandai "tidak tersedia", tidak pernah disimulasikan.

## Mulai di sini

1. **Online dari HP (gratis)**: [`docs/AKSES_HP.md`](docs/AKSES_HP.md) — laptop + Tailscale. Hosting cloud: [`docs/DEPLOY_ONLINE.md`](docs/DEPLOY_ONLINE.md) — Neon → Render → kata sandi → API key AI →
   (opsional) YouTube, otomatisasi, cadangan.
2. **Laptop**: [`docs/MIGRATION_TO_LOCAL_SERVER.md`](docs/MIGRATION_TO_LOCAL_SERVER.md) — paket rilis ZIP,
   `install.ps1`, `start.ps1`, lalu bagian 5e untuk produksi konten.
3. Masalah: [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md). Pemeriksaan keamanan:
   [`docs/SECURITY_CHECKS.md`](docs/SECURITY_CHECKS.md). Keputusan desain: `docs/adr/`.

## Arsitektur singkat

| Bagian | Lokasi | Catatan |
|---|---|---|
| Frontend | `frontend/apps/web` | React + TypeScript + Vite. Di mode local disajikan backend sebagai file statis |
| Avatar | `frontend/packages/avatar` | Paket terpisah. 2D (SVG) dan 3D (talking-avatar + three.js, aset lokal); renderer dipilih otomatis — lihat ADR 0005 |
| Backend | `backend/app` | FastAPI, satu proses; `127.0.0.1` di laptop, `0.0.0.0` + login di mode online |
| Database | `backend/app/db` | SQLite (laptop) atau Postgres/Neon (online), migrasi Alembic, cadangan ZIP berverifikasi |
| Penyedia AI | `backend/app/providers` | `mock` (development, berlabel MOCK) · `ollama` (local) · `nvidia` + cadangan `openrouter` (gratis) · `none` |
| Integrasi | `backend/app/integrations` | Adapter ZOI AI CLIPPER & Blueprint Studio — **read-only**, aplikasi asli tidak diubah |

## Tiga mode

| | `ZOI_MODE=development` | `ZOI_MODE=local` | `ZOI_MODE=online` |
|---|---|---|---|
| Penyedia AI | Mock (jawaban berlabel **MOCK**, tidak pernah membuat statistik) | Ollama lokal; **mock ditolak** | NVIDIA NIM / OpenRouter (gratis) |
| Alamat | Vite `http://127.0.0.1:5173` → backend `:8000` | Satu alamat: `http://127.0.0.1` (port 80) | `https://…onrender.com` (Render free) |
| Database | SQLite | SQLite | Postgres (Neon free), rahasia terenkripsi |
| Login | — | — | Satu kata sandi (wajib) |
| Banner | Pita kuning "DEVELOPMENT MODE" | Tidak ada | Tidak ada |

Mode online untuk membuka ZOI dari HP tanpa laptop; produksi konten (render video, narasi, CLIPPER,
Blueprint) tetap di laptop. Panduan: [`docs/DEPLOY_ONLINE.md`](docs/DEPLOY_ONLINE.md), keputusan desain:
`docs/adr/0012-mode-online.md`.

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

**Produksi konten (laptop)**: paket dari halaman Naskah → Content Production → narasi Piper, salinan
Blueprint Studio dengan tombol *Muat paket ZOI*, render HyperFrames opsional. Lihat `docs/adr/0013-produksi-konten-laptop.md`.

**Otomatisasi**: laporan channel, pantau kompetitor/Trending, pengingat — terjadwal (WIB), hasil di
halaman Automation. Online dibangunkan workflow GitHub Actions `ZOI bangun` (ADR 0014).

**Online (Render + Neon, gratis)**: ikuti [`docs/DEPLOY_ONLINE.md`](docs/DEPLOY_ONLINE.md) —
`Dockerfile` dan `render.yaml` sudah disiapkan di root repo.

## Alat baris perintah

```bash
cd backend
python -m app.cli doctor                         # cek Python, disk, port, frontend, Ollama, path, portabilitas
python -m app.cli data export --exclude-mock     # satu file ZIP berisi semua data + checksum
python -m app.cli data import <file.zip>         # pulihkan (ZOI harus berhenti; data lama di-backup dulu)
python -m app.cli db upgrade | db status | backup
```

## Yang sudah berfungsi (Phase 1–10)

| Fitur | Status |
|---|---|
| Layout command center 5 zona, 17 menu, responsif 375–1440 px | ✅ |
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
| **AI cloud gratis (opsional, bawaan mati):** NVIDIA NIM sebagai penyedia utama, OpenRouter (`:free` saja) sebagai cadangan otomatis; dipilih lewat `.env`; API key di Windows Credential Manager; label "AI cloud" di tiap jawaban | ✅ (diuji dengan server tiruan; layanan asli belum) |
| **Mode online** (Render + Neon): login satu kata sandi, rahasia terenkripsi di database, PWA, tetap terjaga saat dipakai | ✅ (diuji dengan Postgres lokal; Render/Neon asli belum) |
| YouTube versi web (OAuth *Web application*), unduh/pulihkan cadangan dari Settings, paket produksi dari naskah | ✅ (diuji dengan Google tiruan) |
| **Content Production** (laptop): narasi Piper → WAV + SRT, salinan Blueprint Studio dengan tombol *Muat paket ZOI*, render kartu teks HyperFrames opsional | ✅ (Blueprint & HyperFrames diuji sungguhan; Piper dengan tiruan) |
| **Automation**: laporan channel, pantau kompetitor/Trending, pengingat; jadwal WIB, susulan saat bangun, pembangun GitHub Actions, notifikasi di ZOI | ✅ (workflow belum diuji terhadap Render asli) |
| Keamanan: pip-audit & npm audit 0 kerentanan, pemindai rahasia riwayat Git, HSTS/no-store, cakupan tes 93% | ✅ |
| ZOI AI CLIPPER | ditunda — yt-dlp bertentangan dengan ketentuan YouTube; aplikasi tidak diubah |
