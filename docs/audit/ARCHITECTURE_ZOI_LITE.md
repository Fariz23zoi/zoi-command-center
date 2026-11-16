# ARCHITECTURE_ZOI_LITE.md — Arsitektur Realistis untuk AMD E1-6010 / 7 GB RAM / 8 GB disk

Status: USULAN, belum ada kode dan instalasi. Melengkapi ARCHITECTURE.md (arsitektur penuh tetap menjadi tujuan jangka panjang; ZOI Lite adalah **edisi pertama yang benar-benar dibangun**).

## 1. Prinsip ZOI Lite
1. **Semua fitur inti jalan tanpa AI generatif.** AI adalah *plug-in* opsional, bukan fondasi.
2. **Laptop hanya menjalankan:** Python + FastAPI + SQLite + satu tab browser. Tidak ada Node.js, tidak ada server build, tidak ada Ollama.
3. **Hemat RAM & GPU:** avatar 2D sebagai default, 3D hanya jika lolos uji FPS, semua modul berat dimuat hanya saat dipakai.
4. **Jujur:** setiap jawaban berlabel sumbernya — `DATA` (angka nyata), `TEMPLAT` (teks dari templat), `AI` (hanya bila provider AI aktif). Tidak ada data demo.
5. CLIPPER dan Blueprint Studio **tidak diubah**; diakses lewat adapter.
6. ZERO PAID API, ZERO SUBSCRIPTION.

## 2. Diagram

```
LAPTOP (E1-6010, Windows)
┌─────────────────────────────────────────────────────────────────────────┐
│ Browser (Edge efficiency mode / Firefox) — 1 tab                        │
│  ZOI Command Center (frontend SUDAH di-build: HTML/JS/CSS statis)       │
│   · Avatar 2D SVG (default) ─ atau ─ Avatar 3D Lite (dimuat terpisah)   │
│   · Dashboard, Task Manager, Settings, menu fitur                        │
│   · Chat = "Asisten Perintah" (aturan + templat) — AI hanya bila aktif  │
└──────────────▲──────────────────────────────────────────────────────────┘
               │ REST + WebSocket (127.0.0.1:8000)
┌──────────────┴──────────────────────────────────────────────────────────┐
│ Backend ZOI — 1 proses uvicorn, 1 worker, ±100 MB RAM                    │
│  · FastAPI juga menyajikan file frontend statis (tanpa Node)            │
│  · SQLite (WAL) — data/zoi.db, folder data bisa dipindah ke drive lain  │
│  · Task Manager: maks. 1 tugas berat bersamaan, prioritas rendah        │
│  · Intent Router (bahasa Indonesia, aturan + kata kunci) → Tools        │
│  · Tools data: YouTube API, snapshot, statistik, monetisasi, laporan    │
│  · Tools produksi: ClipperAdapter, BlueprintAdapter (paket JSON)        │
│  · Provider AI: [Nonaktif] | Ollama LAN | llama.cpp lokal (eksperimen)  │
│  · Voice (opsional, lazy-load): Piper TTS · faster-whisper tiny         │
│  · Cost Guard: hanya googleapis.com, youtube.com, localhost, IP LAN AI  │
└──────────────┬──────────────────────────────┬───────────────────────────┘
               │                              │
     ZOI AI CLIPPER (tidak diubah)   Blueprint_Studio.html (tidak diubah)
     dijalankan sebagai subprocess   dibuka apa adanya; ZOI hanya
     memakai Python/venv milik       mengekspor paket JSON + naskah
     CLIPPER sendiri                 untuk ditempel/diunggah pengguna

OPSIONAL — KOMPUTER LAIN DI JARINGAN RUMAH (setelah ada hardware)
     Ollama (OLLAMA_HOST di LAN) + model 4B–8B  ←── Provider "Ollama LAN"
```

## 3. Keputusan kunci & alasannya

| Keputusan | Alasan |
|---|---|
| **Frontend di-build di workspace cloud, dikirim sebagai file statis** | Menghemat ±300–400 MB disk (Node + node_modules) dan RAM dev server di laptop |
| **Tes otomatis (Vitest, Playwright, lint) dijalankan di workspace cloud**, bukan di laptop | Chromium Playwright ±150 MB + CPU lambat. Di laptop hanya `zoi doctor` (pemeriksaan ringan) |
| **Tanpa Git di laptop** (opsional) | Unduh rilis ZIP dari GitHub; hemat ±300 MB |
| **Avatar 2D SVG default** | Radeon R2 lemah; SVG + CSS animasi hampir 0 beban GPU, tetap punya 11 status (idle, listening, thinking, speaking dengan mulut sederhana, dll.) |
| **Avatar 3D Lite opsional** | Lihat bagian 4 |
| **Asisten Perintah (tanpa LLM)** sebagai chat default | Router intent berbasis aturan memahami perintah seperti "analisis channel saya", "cek monetisasi", "cari video naik daun niche X", "buat paket video edukasi tentang pesawat" → menjalankan tools nyata → jawaban dari templat + data nyata. Perintah yang tidak dikenali dijawab jujur: "Belum bisa memahami perintah ini tanpa AI. Coba: …" |
| **Provider AI dapat diganti**: `None` (default) · `Ollama LAN` · `llama.cpp lokal` | Ollama tidak dipaksakan. llama.cpp server (MIT) lebih kecil dari Ollama dan bisa ditaruh di drive lain — hanya untuk eksperimen, dengan peringatan kecepatan |
| **Penjadwal ringan** (loop asyncio + tabel jadwal di SQLite) menggantikan APScheduler | Satu dependensi lebih sedikit; automation tetap bisa dijadwalkan/dihentikan/dilog |
| **CLIPPER dipanggil sebagai subprocess** dengan interpreter Python milik CLIPPER sendiri | Tidak perlu memasang dependensi CLIPPER (OpenCV, yt-dlp, dsb.) dua kali → hemat disk; CLIPPER tetap utuh |
| **Blueprint: ekspor paket saja** | HyperFrames tidak dijalankan di laptop ini; renderer tambahan itu aktif nanti di mesin yang lebih kuat |

## 4. Optimasi avatar 3D Lite (hemat RAM & GPU)
- Kode three.js **dipisah (lazy chunk)**: tidak diunduh/dimuat sama sekali saat mode 2D.
- 1 model Rocketbox meshopt < 1 MB, tekstur diperkecil ke 512 px.
- `frameloop="demand"`: render hanya saat ada perubahan; batas 24 fps saat bicara, ±2 fps saat idle.
- `pixelRatio = 1`, kanvas maks. 480×480 px, tanpa antialias, tanpa bayangan, tanpa post-processing, tanpa HDR environment (2 lampu sederhana).
- Render berhenti saat tab tidak terlihat.
- **Uji otomatis saat pertama kali dibuka:** render 5 detik; jika rata-rata < 20 fps atau WebGL gagal → kembali ke 2D, dengan pesan jujur.
- Lip-sync talking-avatar dijalankan hanya selama audio diputar. Beban CPU pada E1-6010 = HYPOTHESIS, diukur saat uji.

## 5. Voice (opsional, dimuat hanya bila diaktifkan)
| Fungsi | Default | Opsi |
|---|---|---|
| Input | **Ketik** | faster-whisper `tiny` int8 (lokal), dengan tombol "tekan untuk bicara" dan batas 15 detik · Web Speech API browser **hanya setelah persetujuan** (audio dikirim ke Google) |
| Output | **Teks** | Suara bawaan Windows lewat `speechSynthesis` (offline, 0 MB tambahan jika paket bahasa Indonesia sudah ada) · Piper (±150 MB) |

Disarankan mulai dari `speechSynthesis` bawaan Windows: tanpa unduhan, dan cukup untuk menggerakkan mulut avatar 2D.

## 6. Pemetaan fitur ZOI Lite

| Fitur | Di ZOI Lite | Label |
|---|---|---|
| Overview, Task Manager, Settings, Memory (catatan & preferensi manual) | Penuh | DATA |
| Channel Analytics, Monetization Tracker, Best Upload Time, Retention | Penuh (butuh OAuth YouTube) | DATA |
| Competitor Intelligence, Viral Video Hunter, Trend Detector | Penuh dari data publik + snapshot berkala | DATA + skor ESTIMATE |
| Content Gap | Perbandingan topik/kata kunci channel vs kompetitor | DATA + ESTIMATE |
| Content Ideas, Script & Storyboard | **Mode Templat**: kerangka beat (pola Blueprint Studio) diisi topik & data; tombol "Tulis dengan AI" nonaktif sampai provider AI aktif | TEMPLAT |
| Automation (laporan harian/mingguan) | Penuh, teks laporan dari templat + angka nyata | DATA |
| ZOI AI CLIPPER | Lewat adapter subprocess; render lambat, 1 job, bisa dibatalkan | — |
| Blueprint Studio | Ekspor paket + naskah; buka Blueprint asli | TEMPLAT |
| AI Assistant (LLM) | Nonaktif — "Butuh provider AI (lihat Settings)" | — |

## 7. Dampak ke PHASE1_PLAN.md (perlu disetujui)
1. Node.js, Git, dan Chromium Playwright **dihapus dari daftar instalasi laptop** (I-2, I-3, I-6). Tetap dipakai di workspace cloud.
2. Instalasi di laptop menjadi: **Python 3.12 (jika belum ada) + venv ±70 MB + ZOI ±10 MB**.
3. `keyring` dan APScheduler ditunda.
4. FastAPI menyajikan frontend statis (`frontend/dist`) — satu perintah `start.ps1` saja.
5. Tambahan di Phase 1: pemeriksaan disk (`zoi doctor`) yang menolak instalasi bila cadangan C: < 5 GB; Settings: lokasi folder data, mode avatar (Auto/2D/3D), provider AI (Nonaktif/Ollama LAN/llama.cpp).
6. Phase 2 (avatar): avatar 2D dulu, 3D Lite setelahnya dengan uji FPS.
7. Phase 3 (AI lokal): diubah menjadi "Provider AI opsional"; tidak ada unduhan model ke laptop ini.

## 8. Jalur naik kelas (tanpa mengubah kode)
ZOI Lite → (tambah komputer AI di LAN, isi alamatnya di Settings) → AI aktif → (laptop baru) → semua modul di satu mesin. Arsitekturnya sama; hanya konfigurasi yang berubah.
