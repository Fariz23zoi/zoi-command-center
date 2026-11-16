# IMPLEMENTATION_PLAN.md — ZOI YouTube Intelligence

Setiap fase berhenti untuk persetujuan. Estimasi durasi = ESTIMATE kerja sesi, bukan janji.

## Pra-syarat sebelum Phase 1 (butuh tindakanmu)
1. **Persetujuan** dokumen audit ini.
2. **Spesifikasi laptop** (perintah PowerShell di HARDWARE_REQUIREMENTS.md) atau hubungkan laptop.
3. **Nama repo baru** untuk ZOI (usulan: `Fariz23zoi/zoi-command-center`, private).
4. Keputusan soal `Perintah.txt`: publikasikan Blueprint Studio sebagai artifact sekarang, atau tunda.
5. (Untuk Phase 6) Google Cloud project gratis + OAuth client "Desktop app" — panduan akan diberikan, **tanpa billing**.

---

## PHASE 1 — FOUNDATION
- **Tujuan:** kerangka backend + frontend + DB + konfigurasi yang bisa jalan di Windows.
- **File:** repo baru `backend/` (FastAPI, SQLAlchemy, Alembic, settings, health endpoint, WebSocket), `frontend/` (Vite React TS, layout command center 5 zona, 16 menu — yang belum jadi berlabel "Segera"), `scripts/check_env.ps1`, `THIRD_PARTY_NOTICES.md`, `COST_CONTROL.md`.
- **Selesai bila:** `start.ps1` menjalankan keduanya; `/api/health` melaporkan status Ollama/FFmpeg/Node/Python secara jujur; migrasi pertama + backup otomatis; layout responsif 375–1440 px tanpa overflow horizontal.
- **Tes:** pytest (health, DB, migrasi), Vitest (layout), Playwright (desktop + mobile).
- **Risiko:** versi Python/Node berbeda di laptop → `check_env.ps1` mendeteksi.

## PHASE 2 — 3D AVATAR
- **Tujuan:** avatar ZOI tampil, bereaksi pada 11 status backend.
- **File:** `frontend/src/avatar/*`, `public/avatars/*.glb`, `public/models/viseme-model.bin`.
- **Selesai bila:** idle/kedip/gerak mata & kepala, ekspresi per status, lip-sync dari file audio uji; ≥30 fps di laptop T1, fallback 2D ringan bila WebGL lemah; keterbatasan animasi tubuh dilabeli.
- **Risiko:** GPU terintegrasi lemah → mode kualitas rendah.

## PHASE 3 — LOCAL AI
- **Tujuan:** `OllamaProvider` + halaman model (aktif, lokasi, koneksi, RAM/VRAM via `/api/ps`, error).
- **Selesai bila:** chat streaming; instruksi instalasi bila Ollama/model tidak ada; `ollama pull` hanya lewat tombol konfirmasi dengan ukuran unduhan; uji 20 prompt Indonesia untuk memilih model default.
- **Risiko:** model kecil lemah di JSON/tool call → validasi skema + retry + parser toleran.

## PHASE 4 — CHAT & VOICE
- **Tujuan:** teks + suara dua arah, ID/EN.
- **Selesai bila:** rekam mic → faster-whisper → teks; Piper → audio → lip-sync; stop/interrupt; kecepatan bicara; riwayat; fallback Web Speech hanya dengan izin.
- **Risiko:** suara Piper Indonesia terbatas/kualitas → fallback speechSynthesis OS.

## PHASE 5 — AI AGENT
- **Tujuan:** Planner, Tool Registry, Task Manager (progress, cancel), Memory (lihat/edit/hapus), Permission Manager, Result Evaluator.
- **Selesai bila:** perintah multi-langkah dipecah jadi task terlihat; tiap tool punya tes; tool `publish` tidak ada / selalu butuh persetujuan.

## PHASE 6 — YOUTUBE INTELLIGENCE
- **Tujuan:** OAuth, Channel Analytics, Competitor, Viral Hunter (snapshot berkala), Trend Detector (dari snapshot sendiri + `videos.list chart=mostPopular regionCode=ID`), Content Gap, Ide, Naskah/Storyboard, Upload Time, Retention, Monetization Tracker.
- **Selesai bila:** semua angka punya sumber + waktu + label; kuota terlihat & dibatasi; mode API/LOCAL/IMPORT/DEMO; ambang YPP disimpan sebagai data yang bisa diperbarui (saat ini: penuh 1.000 subscriber + 4.000 jam tonton publik valid/12 bln atau 10 juta view Shorts/90 hari; expanded 500 subscriber + 3 upload/90 hari + 3.000 jam atau 3 juta view Shorts; **mulai 1 Feb 2027 pelamar baru: 8.000 jam atau 20 juta view Shorts**; watch time Shorts Feed tidak dihitung ke jam tonton).
- **Risiko:** kuota search ±100 panggilan/hari → snapshot hemat & cache.

## PHASE 7 — APPLICATION INTEGRATION
- **Tujuan:** ClipperAdapter + BlueprintAdapter + paket produksi + render HyperFrames lokal.
- **Selesai bila:** baseline CLIPPER & Blueprint lulus uji regresi; perubahan CL-x/BP-x yang disetujui saja.

## PHASE 8 — AUTOMATION
Laporan harian/mingguan, monitoring tren & kompetitor, pengingat produksi, tracking monetisasi — bisa dijadwalkan/dihentikan/dilihat log. Tanpa publikasi otomatis.

## PHASE 9 — TESTING & OPTIMIZATION
Cakupan tes modul inti, uji keamanan (pip-audit, npm audit, gitleaks), profil RAM/GPU, uji mobile.

## PHASE 10 — DEPLOYMENT LOKAL
Panduan instalasi Windows langkah demi langkah, `start.ps1`/`stop.ps1`, backup/restore, troubleshooting.

---

## Definition of Done final
Mengikuti bagian 23 prompt master. Fitur yang tidak bisa jalan tanpa layanan berbayar ditandai **tidak tersedia**, bukan disimulasikan.
