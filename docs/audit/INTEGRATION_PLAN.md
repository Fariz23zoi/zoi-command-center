# INTEGRATION_PLAN.md — ZOI AI CLIPPER & BLUEPRINT STUDIO

Prinsip: **jangan merusak yang sudah berfungsi.** Integrasi dilakukan dari sisi ZOI lewat adapter. Perubahan di dalam CLIPPER / Blueprint Studio hanya yang terdaftar di bawah, masing-masing butuh persetujuan, dilakukan di branch Git terpisah.

---

## 1. ZOI AI CLIPPER

### 1.1 Pola integrasi: library adapter (tanpa mengubah CLIPPER)
ZOI tidak memanggil web Flask-nya; ZOI mengimpor fungsi yang sudah teruji di jalur web mode ZOI:

| Langkah | Fungsi CLIPPER yang dipakai |
|---|---|
| Unduh / cache sumber | `shorts_generator.local.downloader.download_youtube_local(url, fmt)` |
| Transkrip cepat | `shorts_generator.local.transcriber_youtube.transcribe_from_youtube(url, language)` |
| Transkrip fallback (video tanpa subtitle) | `shorts_generator.local.transcriber.transcribe_local(path)` (faster-whisper) |
| Pilih momen (gratis) | `shorts_generator.zoi_engine.analyze_transcript(transcript, n)` |
| Render 9:16 | `shorts_generator.local.clipper.crop_clip_local(src, start, end, "9:16", out, progress_callback)` |

`ClipperAdapter` di ZOI menjalankan fungsi ini di worker Task Manager, meneruskan `progress_callback` ke WebSocket (avatar = EXECUTING), mendukung pembatalan di antara tahap, dan menyimpan hasil ke `production_history`. Flask app CLIPPER tetap bisa dipakai sendiri seperti sekarang.

Syarat teknis: CLIPPER dipasang di venv yang sama (`pip install -e path/ke/zoi-ai-clipper`) **atau** dijalankan sebagai subprocess CLI kecil milik ZOI — dipilih di Phase 7 setelah uji kompatibilitas dependency.

### 1.2 Alur "ZOI, carikan peluang Shorts terbaik"
1. Viral Video Hunter → kandidat video (data publik + skor peluang ESTIMATE).
2. Pengguna memilih video **dan mencentang konfirmasi hak pakai** (milik sendiri / berlisensi / berizin).
3. ClipperAdapter → transkrip → momen → daftar kandidat klip di panel kanan.
4. Pengguna memilih klip → render → preview → unduh. **Tidak ada unggah otomatis.**

### 1.3 Perubahan di CLIPPER yang diusulkan (masing-masing butuh persetujuan)
| # | Perubahan | Alasan | Risiko |
|---|---|---|---|
| CL-1 | Tambah provider `ollama` di `ai_providers.py` + `local/llm.py` (tanpa menghapus provider lain) | AI pemilih momen gratis | Rendah |
| CL-2 | Tambah mode **"ZOI AI (Lokal)"** di UI Flask | Pilihan AI tanpa API berbayar | Rendah |
| CL-3 | Tampilkan `error` di template; hapus duplikasi `app = Flask` | C-01, C-02 | Rendah |
| CL-4 | Tambah `flask` ke requirements; pindahkan `openai`/`google-genai` ke opsional | C-04 | Rendah |
| CL-5 | Sambungkan `subtitle_engine.create_ass` ke render (burn-in subtitle opsional) | Fitur #8 | Sedang — sentuh pipeline render, wajib uji regresi |
| CL-6 | Fallback faster-whisper bila subtitle YouTube tidak ada | Fitur #3 | Sedang |
| CL-7 | Bind `127.0.0.1` default | S-01 | Rendah |
| CL-8 | Pindahkan 14 file `*.before_*`/`*_v*` ke tag Git `pre-zoi-cleanup`, lalu hapus dari tree | C-05 | Rendah (riwayat tetap ada) |
| CL-9 | Keluarkan `output/*.mp3/*.vtt` dari repo | C-06, hak cipta | Rendah |
| CL-10 | Label "Viral Score" → "Skor Peluang (ESTIMATE)" | Aturan akurasi data | Rendah |

Sebelum CL-x apa pun: tag Git `pre-zoi-integration`, uji manual jalur mode ZOI end-to-end, catat hasilnya sebagai baseline.

---

## 2. BLUEPRINT STUDIO

### 2.1 Fakta penentu
Blueprint Studio adalah halaman HTML tunggal tanpa backend yang menghasilkan **prompt**; AI-nya lewat `window.claude.use("sample")` (hanya di claude.ai), render akhirnya dilakukan oleh Claude chat + HyperFrames/Remotion.

### 2.2 Kontrak paket produksi (format bersama)
ZOI menghasilkan `production_package.json` yang memuat persis field yang dipakai Blueprint Studio + yang diminta prompt:
```json
{
  "schema": "zoi.production_package/v1",
  "topic": "Bagaimana pesawat bisa terbang",
  "audience": "Pelajar", "duration_s": 60, "language": "Indonesia",
  "tone": "Edukatif", "aspect_ratio": "9:16", "anti_slop": true,
  "story_mode": "auto",
  "beats": [{"k":"Hook","n":"narasi…","v":"catatan visual…","a":""}],
  "style": {"n":"Cyanotype Teknis","f":"Teknis","d":"…","c":["#0f2a4a","#eaf3ff","#ffd23f"]},
  "narration_text": "…", "srt_words": "…isi SRT per kata…",
  "audio_file": "narasi.wav",
  "output": "hf", "os": "Windows", "storyboard_first": true,
  "research_notes": [{"claim":"…","source":"…","label":"FACT"}],
  "created_at": "2026-11-14T00:00:00+07:00"
}
```
Disimpan di `data/packages/<id>/` bersama `narasi.wav` dan `captions.srt`.

### 2.3 Alur "ZOI, buatkan video edukasi animasi tentang pesawat"
1. **Riset** (LLM lokal + catatan sumber; klaim faktual ditandai FACT/HYPOTHESIS).
2. **Naskah per beat** — memakai aturan penulisan & anti-slop yang **sama** dengan Blueprint Studio (RULES, ANTI, native(), regex SLOP) agar hasil konsisten.
3. **Storyboard** + pilih gaya dari 14 gaya Blueprint Studio.
4. **Narasi lokal:** Piper TTS → `narasi.wav`; **faster-whisper word timestamps → SRT per kata otomatis** (menghapus langkah manual paling rapuh di Blueprint Studio, B-07).
5. **Paket produksi** disimpan + dibuka di Blueprint Studio (pre-filled) **atau** prompt dirakit langsung oleh ZOI.
6. **Render** (pilih):
   - (a) Salin prompt ke Claude (jalur lama — memakai kuota Claude, OPTIONAL), atau
   - (b) LLM lokal menulis komposisi HyperFrames → `npx hyperframes render` lokal → MP4. **Catatan jujur:** kualitas animasi buatan model lokal 8B kemungkinan jauh di bawah Claude (HYPOTHESIS, diuji di Phase 7); jalur (b) dimulai dengan templat komposisi per gaya yang diisi data, bukan kode bebas.
7. ZOI menampilkan hasil + mencatat ke `production_history`.

### 2.4 Perubahan di Blueprint Studio yang diusulkan (butuh persetujuan)
| # | Perubahan | Alasan |
|---|---|---|
| BP-1 | **Impor/ekspor paket JSON** (tombol "Muat paket ZOI" / "Ekspor paket") | Jembatan ke ZOI tanpa mengubah alur lama |
| BP-2 | Provider AI ganda: jika `window.claude` ada → perilaku lama; jika tidak & backend ZOI terdeteksi di `localhost` → `POST /api/llm/json` (Ollama) | ZERO SUBSCRIPTION tanpa merusak versi claude.ai |
| BP-3 | `dl()` fallback ke unduhan `Blob` biasa di luar claude.ai | B-02 |
| BP-4 | Escape di `cards()` | B-03 / S-11 |
| BP-5 | Hapus cabang `"mp4"` mati atau kembalikan opsinya | B-01 |
| BP-6 | Simpan state ke `localStorage` (dibungkus try/catch) | B-05 |
| BP-7 | Opsi Remotion diberi catatan lisensi | Biaya tersembunyi |

### 2.5 Tentang `Perintah.txt`
Permintaan "publikasikan sebagai artifact tanpa mengubah isinya, aktifkan sample & downloads" **belum dijalankan** (Phase 0 = audit saja). Bisa dijalankan kapan pun kamu setujui sebagai tugas terpisah; tidak bentrok dengan integrasi ZOI karena versi artifact tetap memakai jalur claude.ai, sedangkan ZOI menyajikan salinan lokal yang sama.

---

## 3. Urutan & uji
1. Baseline: rekam perilaku CLIPPER mode ZOI dan Blueprint Studio (screenshot + output) sebelum menyentuh apa pun.
2. Adapter ZOI dibuat dan diuji **tanpa** mengubah CLIPPER/Blueprint.
3. Perubahan CL-x / BP-x satu per satu, tiap perubahan = 1 commit + uji regresi baseline.
