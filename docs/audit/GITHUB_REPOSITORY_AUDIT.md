# GITHUB_REPOSITORY_AUDIT.md — Phase 0

Tanggal pemeriksaan: 13 November 2026. Metode: clone dangkal (read-only, tidak dijalankan) untuk repo avatar; halaman GitHub dan sumber publik untuk yang lain. **Tidak ada repo yang di-clone ke proyek dan tidak ada dependency yang diinstal.**

Klasifikasi: **RECOMMENDED** · **REFERENCE ONLY** · **NOT RECOMMENDED**

---

## A. 3D Avatar

### InterviewFlowAI/talking-avatar → **RECOMMENDED**
| Aspek | Temuan (FACT) |
|---|---|
| Tersedia | Ya. Commit terakhir 2 Nov 2026 ("seperated open source 3d avatar and realistic avatars sdk"), paket npm `@interviewflowai/talking-avatar` v0.3.0 |
| Lisensi | **MIT** — mencakup kode, model lip-sync terlatih (`viseme-model.bin`, ±1 MB), dan 2 avatar `.glb` |
| Avatar | Microsoft **Rocketbox** "Business female 04" / "Business male 01" (MIT dari Microsoft), meshopt-compressed < 1 MB, punya viseme Oculus + blendshape ARKit |
| Cara kerja | Model kecil di browser mendengarkan **audio apa pun** (TTS, mikrofon) → viseme. Tanpa server, tanpa API key, tanpa timing fonem |
| Dependency | peer: `three >=0.160`, `react >=18` (opsional). Dev: vite, typescript |
| API berbayar | **Tidak ada.** Default memuat model dari jsDelivr — bisa di-self-host (wajib untuk mode lokal/offline) |
| Kompatibilitas | Cocok dengan Piper TTS (audio lokal) → lip-sync tanpa cloud |
| Keterbatasan | Proyek muda (v0.x). Dibingkai untuk **close-up wajah** — animasi tubuh penuh tidak disediakan. Model dilatih pada ucapan bahasa Inggris yang jelas; kualitas lip-sync bahasa Indonesia = **HYPOTHESIS, harus diuji** |
| Komersial | Diizinkan (MIT) |

### riverbornai/Interactive-3D-avatar-ai-agent → **NOT RECOMMENDED** (boleh dibaca sebagai referensi pemetaan blendshape)
| Aspek | Temuan (FACT) |
|---|---|
| Tersedia | Ya, 1 commit "Initial public release" 2 Okt 2026 |
| Lisensi | MIT |
| Dependency wajib | `openai`, `elevenlabs`, `azure-cognitiveservices-speech`; `.env.example` meminta **OPENAI_API_KEY, DEEPGRAM_API_KEY, AZURE_SPEECH_KEY, ELEVENLABS_API_KEY** |
| Avatar | `avatar_fixed.glb` (4,7 MB) dari **Ready Player Me** — layanan RPM **ditutup 31 Jan 2026** setelah diakuisisi Netflix; lisensi aset tidak dicantumkan di repo |
| Alasan ditolak | Seluruh jalur inti (LLM, STT, TTS, viseme) bergantung pada 4 layanan berbayar yang secara eksplisit dilarang prompt |

## B. 3D Web Engine
| Repo | Lisensi | Status | Klasifikasi |
|---|---|---|---|
| mrdoob/three.js | MIT | Aktif, standar industri | **RECOMMENDED** |
| pmndrs/react-three-fiber | MIT | Aktif | **RECOMMENDED** |
| pmndrs/drei (helper R3F) | MIT | Aktif | **RECOMMENDED** (opsional, ambil seperlunya) |
| pixiv/three-vrm | MIT | Aktif | **REFERENCE ONLY** — jalur alternatif jika ZOI dibuat sebagai karakter VRM (VRoid Studio gratis; lisensi tiap model VRM ditentukan pembuatnya) |

## C. YouTube Analytics
### sasank-in/yt-analytics-hub ("Creatorscope") → **REFERENCE ONLY**
- MIT, FastAPI + SQLAlchemy 2 + SQLite, YouTube Data API v3 (API key, tanpa scraping), tanpa layanan berbayar.
- Kematangan rendah: 21 commit, 1 bintang. Frontend vanilla JS + Tailwind CDN (tidak cocok dengan stack React kita).
- Layak dipinjam polanya: *skip refetch dalam jendela waktu*, skema penyimpanan video/channel, endpoint analitik. "RPM-based earnings estimate" → di ZOI wajib berlabel **ESTIMATE**.

### yaskovbs/YouTube-Dashboard → **NOT RECOMMENDED** untuk dipakai kodenya
- **Tidak ada file LICENSE** → secara hukum semua hak dilindungi; kodenya tidak boleh disalin.
- 2 commit, 0 bintang, antarmuka Hebrew RTL, port TypeScript untuk Cloudflare Pages.
- Ide fitur (best weekday, Shorts vs long-form, cache 10 menit) boleh dijadikan inspirasi, ditulis ulang sendiri.

## D. Video Processing
| Repo | Lisensi | Catatan | Klasifikasi |
|---|---|---|---|
| yt-dlp/yt-dlp | Unlicense | Sudah dipakai CLIPPER. YouTube kini butuh JS runtime (Node/Deno) — sudah ditangani via `js_runtimes`. Pakai sesuai ToS: utamakan konten sendiri/berizin | **RECOMMENDED** |
| SYSTRAN/faster-whisper | MIT | Sudah ada di CLIPPER (CLI). Model Whisper dari OpenAI berlisensi MIT | **RECOMMENDED** |
| FFmpeg/FFmpeg | LGPL-2.1+ (GPL jika build memakai komponen GPL, mis. libx264) | Dipakai sebagai program terpisah (bukan di-link) → aman untuk pemakaian pribadi | **RECOMMENDED** |

## E. Animated Video Engine
| Repo | Lisensi | Catatan | Klasifikasi |
|---|---|---|---|
| givemotion/givemotion | MIT | Code-to-video untuk agent, Node 20+ + Chrome + ffmpeg, lokal, tanpa akun. **0 bintang**, kematangan belum terbukti | **REFERENCE ONLY** |
| heygen-com/hyperframes *(sudah dipakai Blueprint Studio)* | **Apache-2.0** | HTML+GSAP → MP4 deterministik, lokal, Node ≥22 + FFmpeg. Komunitas besar | **RECOMMENDED** sebagai mesin render Blueprint Studio |
| remotion-dev/remotion *(opsi di Blueprint Studio)* | Remotion License (source-available) | Gratis hanya untuk individu / perusahaan ≤3 orang | **OPTIONAL — risiko biaya**, jangan jadi default |

## F. Local AI & Voice
| Repo | Lisensi | Catatan | Klasifikasi |
|---|---|---|---|
| ollama/ollama | MIT | Runtime LLM lokal, tool calling, API di port 11434. **Hati-hati:** Ollama juga punya model "cloud" — dilarang dipakai | **RECOMMENDED** |
| OHF-Voice/piper1-gpl | **GPL-3.0** | Penerus resmi Piper (repo `rhasspy/piper` diarsipkan Okt 2025). Gratis, CPU real-time. Jalankan sebagai proses terpisah | **RECOMMENDED** |
| rhasspy/piper | MIT (diarsipkan) | Tidak menerima update | **NOT RECOMMENDED** |

## G. Aplikasi milik sendiri
| Repo | Klasifikasi |
|---|---|
| Fariz23zoi/zoi-ai-clipper | **WAJIB DIPERTAHANKAN** — diintegrasikan lewat adapter, bukan ditulis ulang |
| Blueprint_Studio.html | **WAJIB DIPERTAHANKAN** — diintegrasikan lewat kontrak paket produksi |
| SamurAIGPT/AI-Youtube-Shorts-Generator (asal CLIPPER) | REFERENCE ONLY — notice MIT-nya wajib tetap ada di CLIPPER |

## Ringkasan: komponen yang akan diambil
Hanya paket npm/pip resminya, **tanpa meng-clone repo utuh**: `three`, `@react-three/fiber`, sebagian `@react-three/drei`, `@interviewflowai/talking-avatar` (+ self-host model & avatar), `ollama` (aplikasi), `faster-whisper`, `piper-tts`, `yt-dlp`, FFmpeg biner, `hyperframes` (CLI, saat render).
