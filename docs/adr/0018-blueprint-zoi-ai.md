# ADR 0018 — Blueprint Studio memakai AI ZOI, animasi dibuat ZOI AI

Status: diterima (18 Nov 2026, izin pemilik) · Versi 1.2.6

## Konteks
Blueprint Studio (file milik pengguna, dari tutorial YouTube) memakai `claude.use("sample")` yang hanya ada di dalam
Claude, sehingga di salinan ZOI muncul "Fitur AI tidak tersedia". Alur tutorial: cerita → TTS ElevenLabs + SRT →
prompt motion → Claude membuat animasi HTML/HyperFrames/Remotion → render. Pemilik ingin semua diproses ZOI AI.

## Keputusan
- File asli tetap hanya dibaca. Salinan mendapat shim `window.claude.use("sample"|"downloads")`:
  `sample.json(prompt)` → `POST /api/production/blueprint/ai` → AI Brain ZOI (NVIDIA NIM / OpenRouter :free / Ollama
  sesuai `.env`); prompt Blueprint tidak diubah. Gagal → Blueprint memakai cara cadangan bawaannya.
- Tombol **🎬 Kirim ke ZOI** di salinan: cerita + gaya (prompt motion, atau gaya terpilih) → paket produksi.
- Content Production: **Buat narasi** (Piper, pengganti ElevenLabs + SRT) → **🎬 Animasikan dengan ZOI AI**: AI ZOI
  menulis adegan per beat (HTML/SVG + CSS @keyframes), disaring ketat (daftar izin tag/atribut, tanpa script/URL;
  hanya `url(#id)` lokal), dirangkai ZOI dengan waktu narasi + subtitle → HyperFrames → `video.mp4`.
  Adegan yang gagal disaring → kartu teks (dicatat di hasil tugas).
- Renderer tetap HyperFrames (Apache-2.0, sudah dipakai ZOI). Remotion tidak dipakai: butuh build React per video
  dan lisensinya berbayar untuk perusahaan; lebih berat untuk laptop 2 core.

## Batasan
Kualitas adegan bergantung model gratis yang dipakai; model kecil bisa menghasilkan adegan sederhana atau gagal.
Sidik salinan Blueprint kini mencakup sisipan ZOI → salinan dibuat ulang otomatis setelah update.
