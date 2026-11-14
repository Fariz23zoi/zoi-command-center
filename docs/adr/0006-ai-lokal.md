# ADR 0006 — AI lokal (Ollama): hanya membaca, tidak pernah mengunduh

**Status:** diterima (14 Nov 2026). Keputusan pengguna: K-1 "ZOI tidak pernah mengunduh model",
K-2 "model aktif boleh dipilih dari UI".

**Keputusan.**
- ZOI hanya **membaca** dari Ollama (`/api/version`, `/api/tags`, `/api/ps`, `/api/show`) dan memakai
  `/api/chat` serta `/api/generate` dengan `keep_alive: 0` (melepas model dari memori, file tetap ada).
- Endpoint yang mengubah file model (`/api/pull`, `/api/delete`, `/api/push`, `/api/create`, `/api/copy`,
  `/api/blobs`) **diblokir di klien** lewat event hook httpx, setelah Cost Guard. Tes memastikan blokir ini.
- Model cloud Ollama ditolak: tag `:cloud`/`-cloud` atau entri yang membawa `remote_model`/`remote_host`.
- Model aktif: pilihan di Settings › AI Lokal (tabel `app_meta`, ikut ekspor) → `ZOI_OLLAMA_MODEL` → tidak ada.
  Saat dipilih, model divalidasi: terpasang, bukan cloud, punya kemampuan `completion`.
- Kode di luar `app/providers` tidak mengenal Ollama: `LocalModelAdmin` (Protocol) di `providers/base.py`,
  `LocalAIService` di `app/ai/local.py`. Uji model memakai instance terpisah (`with_model`) agar chat tidak terganggu.
- Riwayat chat dipotong ke ±60% jendela konteks (perkiraan 3,5 karakter/token). Konteks dibaca dari `/api/ps`
  bila model sedang dimuat; selain itu 4096 (default Ollama). ZOI tidak mengubah `num_ctx` agar RAM tetap kecil.
- Model berkemampuan `thinking` mendapat `think: true`; proses berpikir disimpan di kolom `messages.thinking`
  dan ditampilkan terlipat. `<think>…</think>` di dalam isi jawaban juga dipisahkan (tahan tag terpotong).
- Keluaran terstruktur: JSON schema dikirim sebagai `format`, divalidasi Pydantic, 1× percobaan ulang dengan
  alasan kegagalan. Mock mengisi teks `[MOCK]` dan **menolak** mengarang angka.
- Uji kecocokan model: 20 prompt tetap (`app/ai/eval_prompts.json`, versi 1). Diukur: waktu ke token pertama
  (jam dinding), token/detik dan jumlah token (dari Ollama), validitas JSON, ketepatan tool. Kualitas jawaban
  percakapan dinilai pengguna. Mock tidak boleh diuji. Hasil disimpan di `model_evaluations` bersama nama
  komputer dan versi Ollama.
- Katalog model kandidat adalah data statis di repo (`app/ai/catalog.json`), dicek dari ollama.com/library
  pada 14 Nov 2026 — ZOI tidak mengambil daftar model dari internet.

**Konsekuensi.**
- Semua tes memakai Ollama tiruan (`backend/tests/fake_ollama.py`, juga sebagai server HTTP untuk E2E).
  Uji dengan Ollama sungguhan baru terjadi saat migrasi (checklist di `MIGRATION_TO_LOCAL_SERVER.md`).
- Membatalkan uji model hanya berlaku di antara prompt; prompt yang sedang berjalan diselesaikan dulu.
- Gemma 4 di Ollama jauh lebih besar dari namanya (e2b ±4,3–7,5 GB) — dicatat di katalog.
