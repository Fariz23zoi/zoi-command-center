# LICENSE_COMPLIANCE.md — Phase 0

Saya bukan pengacara; dokumen ini adalah inventaris lisensi teknis untuk pemakaian **pribadi, lokal, self-hosted**. Jika ZOI kelak didistribusikan atau dijual, tinjau ulang baris bertanda ⚠️.

## 1. Perangkat lunak

| Komponen | Lisensi | Kewajiban utama | Status |
|---|---|---|---|
| ZOI AI CLIPPER (turunan SamurAIGPT) | MIT © Anil Chandra Naidu Matcha | Pertahankan file LICENSE & notice hak cipta | ✅ (notice masih ada) |
| Blueprint Studio | Milik sendiri, belum ada LICENSE | Tambahkan LICENSE bila akan dibagikan | ⚠️ |
| three.js, React Three Fiber, drei | MIT | Notice | ✅ |
| talking-avatar (kode + model viseme) | MIT | Notice | ✅ |
| React, Vite, TypeScript | MIT / Apache-2.0 | Notice | ✅ |
| FastAPI, SQLAlchemy, Alembic, Pydantic | MIT | Notice | ✅ |
| Ollama | MIT | Notice | ✅ |
| faster-whisper | MIT | Notice | ✅ |
| yt-dlp | Unlicense | — | ✅ |
| FFmpeg | LGPL-2.1+ / GPL (tergantung build) | Dipanggil sebagai program terpisah, jangan di-link statis | ✅ pribadi · ⚠️ distribusi |
| OpenCV (opencv-python) | Apache-2.0 | Notice | ✅ |
| Piper (`piper-tts`, OHF-Voice/piper1-gpl) | **GPL-3.0** (+ espeak-ng GPL) | Jika ZOI didistribusikan bersama Piper, kode yang menyatu harus GPL-compatible. **Mitigasi:** jalankan Piper sebagai proses/servis terpisah lewat CLI/HTTP | ✅ pribadi · ⚠️ distribusi |
| HyperFrames | Apache-2.0 | Notice | ✅ |
| GSAP | Lisensi standar GSAP (gratis, bukan OSI) | Patuhi syarat GSAP; jangan untuk produk yang bersaing dengan Webflow | ✅ pribadi |
| Remotion | Remotion License (source-available) | Gratis hanya individu / perusahaan ≤3 orang | ⚠️ OPTIONAL |
| APScheduler | MIT | Notice | ✅ |

## 2. Model AI

| Model | Lisensi | Catatan |
|---|---|---|
| **Qwen3** (semua ukuran) | Apache-2.0 | ✅ Pilihan utama |
| **Gemma 4** (E2B, E4B, 12B, 26B MoE, 31B) | **Apache-2.0** (pertama kali untuk Gemma, rilis 2 Apr 2026) | ✅ Alternatif utama |
| Llama 3.x / 4 | Llama Community License (kustom, ada ambang komersial) | ⚠️ REFERENCE — tidak dijadikan default |
| Whisper (bobot untuk faster-whisper) | MIT | ✅ |
| Suara Piper (`rhasspy/piper-voices`) | **Berbeda per suara** — tiap suara punya MODEL_CARD sendiri | ⚠️ Periksa MODEL_CARD suara bahasa Indonesia sebelum dipakai |
| Suara Piper `id_ID-news_tts-medium` (dicek 14 Nov 2026) | Repo MIT; MODEL_CARD menunjuk dataset Kaggle "indic-tts-malayalam-speech-corpus" dengan lisensi "See URL"; di-fine-tune dari `en_US-lessac-medium` | ⚠️ **Asal-usul data tidak jelas.** Keputusan pengguna (Phase 4 K-1): boleh untuk pemakaian pribadi setelah catatan diterima di Settings › Suara; **jangan dipakai sebagai suara di video yang dipublikasikan**. Tanpa persetujuan, backend menolak `/api/voice/speak` |
| faster-whisper 1.2.1 + PyAV 18 + CTranslate2 + onnxruntime | MIT / BSD-3 / MIT / MIT | Paket opsional (`requirements-voice.txt`), tidak ikut paket inti | ✅ |
| `viseme-model.bin` (talking-avatar) | MIT | ✅ |

## 3. Aset

| Aset | Lisensi | Catatan |
|---|---|---|
| Avatar Rocketbox (female/male) | MIT (Microsoft Rocketbox) | ✅ Boleh dimodifikasi untuk identitas ZOI |
| Avatar Ready Player Me (repo riverbornai) | Tidak jelas; layanan sudah tutup | ❌ Jangan dipakai |
| Model VRM dari VRoid Hub | Ditentukan pembuat tiap model | ⚠️ Periksa per model |
| Animasi Mixamo | Gratis (akun Adobe), boleh dipakai dalam proyek; file mentah tidak boleh didistribusikan ulang | ⚠️ Opsional; jangan commit file mentahnya ke repo publik |
| Font Bricolage Grotesque (Blueprint Studio) | SIL OFL 1.1 | ✅ Sebaiknya di-self-host untuk mode offline |
| Haar cascade OpenCV | BSD-3 (Intel) | ✅ |

## 4. Konten video (paling berisiko)
- Video YouTube publik **tidak otomatis boleh** diunduh, dipotong, diunggah ulang, atau dimonetisasi. ZOI tidak akan membuat fitur untuk menghindari Content ID.
- CLIPPER saat ini meng-commit `output/audio-test.mp3` dan transkrip VTT video pihak ketiga ke Git → disarankan dikeluarkan dari riwayat repo (butuh persetujuanmu, karena mengubah riwayat Git).
- ZOI akan menampilkan peringatan sumber + checkbox "konten ini milik saya / berlisensi / berizin" sebelum render CLIPPER.

## 5. Tindakan yang menunggu persetujuan
1. Tambah `THIRD_PARTY_NOTICES.md` di repo ZOI (Phase 1).
2. Tambah LICENSE untuk Blueprint Studio (pilih: MIT / pribadi).
3. Bersihkan media pihak ketiga dari repo CLIPPER.
