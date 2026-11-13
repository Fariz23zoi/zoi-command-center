# COST_CONTROL.md — Phase 0

Prinsip: ZERO PAID API · ZERO SUBSCRIPTION · tidak ada transaksi, trial, atau pembelian kuota otomatis.

## 1. Klasifikasi seluruh komponen

### FREE LOCAL (tanpa biaya layanan)
Ollama + Qwen3/Gemma 4 · faster-whisper · Piper TTS · talking-avatar + avatar Rocketbox · Three.js / R3F · React + Vite · FastAPI · SQLite/SQLAlchemy/Alembic · FFmpeg · OpenCV · yt-dlp · HyperFrames · APScheduler · Pandas/Plotly · ZOI AI CLIPPER mode ZOI · Blueprint Studio (fallback templat).

### FREE WITH LIMITS
| Komponen | Batas | Penanganan di ZOI |
|---|---|---|
| YouTube Data API v3 | Default 10.000 unit/hari; `search.list` punya bucket terpisah ±100 panggilan/hari; `videos.list`/`channels.list` 1 unit | Penghitung kuota lokal, cache, ganti `search.list` dengan `playlistItems.list` bila bisa, berhenti saat habis, tunggu reset (tengah malam waktu Pasifik ≈ 14.00–15.00 WIB) |
| YouTube Analytics API (OAuth) | Kuota gratis Google Cloud | Hanya data channel sendiri |
| Google Cloud project | Gratis untuk API YouTube | **Jangan aktifkan billing account** — tidak diperlukan |
| Web Speech API Chrome (fallback STT) | Gratis, tetapi **audio dikirim ke server Google** | Hanya aktif setelah persetujuan eksplisit; default faster-whisper |
| Browser speechSynthesis (fallback TTS) | Gratis; suara bergantung OS | Fallback saja |
| jsDelivr / Google Fonts CDN | Gratis | Self-host untuk mode offline |
| Blueprint Studio `claude.use("sample")` | Memakai kuota paket Claude yang sudah ada | Tetap tersedia sebagai opsi; default ZOI = Ollama |

### OPTIONAL PAID (tidak wajib, nonaktif secara default)
| Komponen | Alasan |
|---|---|
| Remotion | Lisensi berbayar bila organisasi ≥4 orang |
| Hosting/VPS/domain | Hanya jika ingin diakses dari luar rumah |
| Mixamo | Gratis tetapi butuh akun Adobe |

### NOT ALLOWED (tidak boleh dipakai di ZOI)
OpenAI API · Anthropic API (Claude API key) · Gemini API · MuAPI · ElevenLabs · Deepgram · Azure Speech · Ready Player Me · **Ollama Cloud models** (tag `:cloud`) · API YouTube pihak ketiga berbayar (OutlierKit, dsb.) · layanan scraping berbayar · cloud database berbayar.

## 2. Dependency berbayar yang SUDAH ADA di aplikasi lama

| Lokasi | Dependency | Tindakan yang diusulkan (butuh persetujuan) |
|---|---|---|
| CLIPPER `main.py` default `--mode api` | MuAPI | Biarkan apa adanya; ZOI tidak memanggil jalur ini |
| CLIPPER mode CLAUDE/CHATGPT/HYBRID | Anthropic & OpenAI API | Tetap ada tetapi ZOI menandai **NOT ALLOWED**; tambah provider `ollama` |
| CLIPPER `--mode local` | OpenAI / Gemini wajib | Tambah provider `ollama` sebagai default |
| CLIPPER `requirements-local.txt` | `openai`, `google-genai` | Pindahkan ke `requirements-optional.txt` |
| Blueprint Studio | `claude.use("sample")` | Tambah provider Ollama via backend ZOI, pertahankan jalur claude.ai |

## 3. Biaya non-software yang tetap ada (jujur)
- **Listrik:** inferensi LLM lokal + render video membebani CPU/GPU. ESTIMATE: laptop 45–150 W saat inferensi.
- **Internet:** unduh model sekali (Qwen3 8B ±5 GB, Whisper small ±0,5 GB, suara Piper ±60 MB), data YouTube, unduh video.
- **Perangkat keras:** RAM 16 GB disarankan. Upgrade RAM/SSD adalah biaya opsional.
- **Penyimpanan:** video sumber & hasil render cepat memakan puluhan GB.
- **Domain/hosting:** opsional, tidak diperlukan untuk LOCAL MODE.

## 4. Pengaman yang akan dibangun (Phase 1+)
1. `COST_GUARD` di backend: daftar host yang diizinkan (googleapis.com, youtube.com, localhost). Panggilan ke host lain diblokir dan dicatat.
2. Validasi model Ollama: tolak tag `:cloud` / remote.
3. Penghitung kuota YouTube lokal dengan batas keras.
4. Tidak ada field "API key berbayar" di UI Settings.
5. Tes otomatis yang gagal bila ada import `openai`, `anthropic`, `google.genai`, `elevenlabs`, `deepgram`, `azure` di kode ZOI.
