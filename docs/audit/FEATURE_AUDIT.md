# FEATURE_AUDIT.md — ZOI YouTube Intelligence (Phase 0)

Tanggal audit: 13 November 2026 · Auditor: Claude · Status: **AUDIT SAJA, tidak ada kode yang diubah**

Label data: **FACT** = diperiksa langsung · **ESTIMATE** = perkiraan dengan metode tertulis · **HYPOTHESIS** = dugaan yang harus diuji.

---

## 1. Apa saja yang diaudit

| Objek | Status akses | Hasil |
|---|---|---|
| `Fariz23zoi/zoi-ai-clipper` (private) | FACT — di-clone, commit `29d1738` (11 Nov 2026, "snapshot untuk audit") | Diaudit penuh, 46 file, ±6.100 baris |
| BLUEPRINT STUDIO | FACT — file `Blueprint_Studio.html` + `Perintah.txt` diunggah pengguna (tidak ada di GitHub/Drive) | Diaudit penuh, 250 baris |
| Laptop pengguna | **Tidak terhubung** (bridge desktop offline saat audit) | Spesifikasi belum diketahui — lihat HARDWARE_REQUIREMENTS.md |
| Repo ZOI utama (command center) | Belum ada — belum dibuat | Akan dibuat di Phase 1 setelah disetujui |

Repo lain di akunmu (`Fariz23zoi/Fariz23zoi`, `skills` (fork), `Laporan--sungai`) tidak terkait proyek ini.

---

## 2. ZOI AI CLIPPER — kondisi aktual

### 2.1 Asal-usul (FACT)
- Turunan dari **SamurAIGPT/AI-Youtube-Shorts-Generator**, lisensi **MIT**, `Copyright (c) 2026 Anil Chandra Naidu Matcha`. Notice lisensi wajib dipertahankan.
- README masih README asli (promosi MuAPI, "pay only for API usage"), belum mencerminkan ZOI.
- Ada skill `.claude/skills/youtube-shorts-generator` yang masih menunjuk ke MuAPI (berbayar).

### 2.2 Dua aplikasi dalam satu repo (FACT)

| Entry point | Teknologi | Jalur | Status biaya |
|---|---|---|---|
| `app.py` (web, port 5000) | Flask | Mode **ZOI** (heuristik lokal) | **GRATIS LOKAL** |
| `app.py` | Flask | Mode CLAUDE / CHATGPT / HYBRID | **BERBAYAR** (Anthropic API, OpenAI API) |
| `main.py` (CLI) `--mode api` (**default**) | MuAPI | download/transkripsi/LLM/crop di cloud | **BERBAYAR** (MuAPI pay-per-call) |
| `main.py --mode local` | yt-dlp + faster-whisper + ffmpeg/OpenCV | LLM via OpenAI / Gemini / Claude | **Sebagian berbayar** (LLM cloud wajib) |

**Kesimpulan:** satu-satunya jalur yang 100% gratis dan lokal hari ini adalah **web app mode ZOI**. Jalur CLI default justru berbayar.

### 2.3 Pipeline web app mode ZOI (FACT)
1. `download_youtube_local()` — yt-dlp, cache `output/source_<id>.mp4`, maks 720p, butuh Node.js (`js_runtimes`).
2. `transcribe_from_youtube()` — **mengambil subtitle YouTube** (id lalu en) via yt-dlp, parse VTT per kata. **Tidak memakai faster-whisper.** Gagal jika video tidak punya subtitle id/en.
3. `zoi_engine.analyze_transcript()` (label UI "ZOI ENGINE V4.1") — heuristik kata kunci bahasa Indonesia (hook/konflik/payoff/event), jendela 45/60/75 detik, dedupe overlap ≥40%. Tanpa AI.
4. Pengguna memilih klip → `crop_clip_local()` di thread background: ffmpeg potong → OpenCV Haar-cascade face tracking crop 9:16 → mux audio. Fallback tanpa OpenCV: blur background (dibuat untuk Android/Termux).
5. Progress polling `/progress/<job_id>`, preview + download MP4.

### 2.4 Daftar fitur vs yang diharapkan prompt

| # | Fitur | Status | Catatan |
|---|---|---|---|
| 1 | Input URL YouTube | ✅ Berfungsi | Juga menerima path lokal (lihat risiko keamanan) |
| 2 | Analisis video | ⚠️ Teks saja | Tidak ada analisis visual/audio |
| 3 | Transkripsi | ⚠️ Sebagian | Web app: subtitle YouTube saja. faster-whisper hanya di CLI `--mode local` |
| 4 | Pemilihan momen | ✅ Heuristik lokal; ⛔ AI hanya via API berbayar | Belum ada provider Ollama |
| 5 | Timestamp | ✅ | |
| 6 | Storyboard | ❌ Tidak ada | |
| 7 | Vertical crop | ✅ | Haar cascade (ringan, akurasi terbatas) |
| 8 | Subtitle | ❌ Belum tersambung | `local/subtitle_engine.py` (`create_ass`) ada tetapi **tidak dipanggil** di mana pun |
| 9 | Video preview | ✅ | |
| 10 | Export Shorts | ✅ MP4 720×1280 | |
| — | Viral Score 0–100 | ⚠️ | Skor heuristik; harus diberi label **ESTIMATE**, bukan prediksi viral |
| — | Pembatalan job | ❌ | Thread daemon, tidak bisa dibatalkan |
| — | Tes otomatis | ❌ Tidak ada | |

### 2.5 Masalah kode yang ditemukan (FACT, belum diperbaiki — sesuai aturan Phase 0)

| ID | Masalah | Dampak |
|---|---|---|
| C-01 | `app = Flask(__name__)` dan import Flask ditulis **dua kali** di `app.py` | Tidak fatal, tapi tanda patch bertumpuk |
| C-02 | Variabel `error` dikirim ke template tetapi template **tidak menampilkannya** | Kegagalan analisis terlihat seperti halaman kosong — pengguna tidak tahu error |
| C-03 | Fungsi `sample_clips()` berisi **data palsu** (klip contoh, skor palsu) | Tidak dipakai saat ini, tetapi melanggar aturan "jangan membuat data palsu" bila tersambung |
| C-04 | `flask` **tidak tercantum** di `requirements*.txt` | Instalasi baru akan gagal |
| C-05 | **14 file cadangan** (`*.before_*`, `zoi_engine_v2/v3_1/v3_2_1/before_v4/backup`, `clipper_before_*`, `transcriber_youtube.backup`) | Membingungkan; seharusnya diganti riwayat Git |
| C-06 | `output/audio-test.mp3` (12,9 MB) dan transkrip VTT video pihak ketiga ter-commit, padahal `output/` ada di `.gitignore` | Repo membengkak; potensi masalah hak cipta konten orang lain |
| C-07 | `.gitignore` berisi entri duplikat | Kosmetik |
| C-08 | `local/llm.py` fallback provider = `"claude"` sementara `config.py` default `"openai"` | Perilaku tidak konsisten |
| C-09 | Job render disimpan di dict memori (`RENDER_JOBS`) | Hilang saat restart; tumbuh tanpa batas |
| C-10 | README & skill `.claude` masih mempromosikan MuAPI | Bertentangan dengan aturan ZERO PAID API |

---

## 3. BLUEPRINT STUDIO — kondisi aktual

Sumber: `Blueprint_Studio.html` (250 baris) + `Perintah.txt` yang kamu unggah di tengah audit. Tidak ada di GitHub/Drive — saat ini hanya ada sebagai satu file HTML.

### 3.1 Apa itu (FACT)
Aplikasi satu halaman (HTML + CSS + JavaScript murni, tanpa build, tanpa backend) untuk mengubah **topik → cerita per beat → gaya visual → PROMPT** yang kemudian **disalin manual ke chat Claude** untuk membangun animasinya. Blueprint Studio sendiri **tidak merender video**.

Alur 4 langkah:
1. **Ide** — topik, durasi (30/60/90 dtk), audiens, nada, bahasa (ID/EN), rasio (16:9, 9:16, 1:1), toggle *Anti slop*.
2. **Cerita** — mode otomatis (AI) atau manual (tempel narasi → dipecah jadi beat). Tiap beat: narasi, catatan visual, aset foto. Tombol *Ulang* per beat.
3. **Gaya** — 14 gaya bawaan (Cyanotype, Isometrik, Papan Tulis, dll.) + tombol *Kejutkan aku* (AI membuat gaya baru).
4. **Mode & prompt** — naskah untuk TTS, kolom tempel **SRT per kata**, pilihan hasil: Animasi HTML / MP4 via **HyperFrames** / MP4 via **Remotion**, tutorial per OS, toggle *Storyboard dulu* → menghasilkan prompt panjang.

### 3.2 Ketergantungan (FACT)

| Ketergantungan | Fungsi | Status biaya / risiko |
|---|---|---|
| `window.claude.use("sample")` | Menulis cerita, menulis ulang beat, pembersih anti-slop, gaya "Kejutkan aku" | **Hanya jalan di runtime artifact claude.ai** dan memakai kuota paket Claude milikmu. Di luar claude.ai → fallback ke templat (jujur, ada pesan "Penulisan AI tidak tersedia") |
| `window.claude.use("downloads")` | Unduh naskah/prompt .txt | Hanya di claude.ai. Di browser biasa tombol unduh **diam tanpa reaksi** (bug B-02) |
| Google Fonts (Bricolage Grotesque) | Tipografi | Gratis, OFL; membuat request ke server Google |
| Langkah TTS | "Salin narasi ke alat text-to-speech, tempel SRT" | Alat TTS eksternal **tidak ditentukan** — pengguna bisa tergoda memakai layanan berbayar |
| Render akhir | Prompt ditempel ke chat Claude | Bergantung pada chat Claude (langganan) |
| HyperFrames (HeyGen) | HTML → MP4 | **Apache-2.0**, gratis, lokal (Node ≥22 + FFmpeg + Chrome headless) → aman |
| Remotion | React → MP4 | **Source-available, BUKAN open source.** Gratis untuk individu & perusahaan ≤3 orang; perusahaan 4+ orang wajib lisensi berbayar → tandai **OPTIONAL / berisiko biaya** |
| GSAP (CDN jsDelivr, dipakai prompt HyperFrames) | Animasi | Gratis dipakai; lisensi standar GSAP (bukan OSI) |

### 3.3 `Perintah.txt` (FACT)
Isi: *"Publikasikan sebagai artifact tanpa mengubah isinya. Aktifkan kemampuan sample dan downloads."*
→ Ini **instruksi deployment**, bukan audit. Sesuai aturan Phase 0 ("jangan mengaktifkan layanan eksternal", "berhenti dan tunggu persetujuan") **belum dijalankan**. Menerbitkannya sebagai artifact claude.ai sendiri tidak menimbulkan biaya baru di luar paket Claude yang sudah kamu punya, tetapi fitur AI-nya memakai kuota Claude — bukan AI lokal. Siap dijalankan begitu kamu setujui (terpisah dari Phase 1).

### 3.4 Masalah yang ditemukan (FACT, belum diperbaiki)

| ID | Masalah | Dampak |
|---|---|---|
| B-01 | Cabang `if($("hasil").value==="mp4")` tidak pernah jalan — opsi "mp4" tidak ada di dropdown (nilainya `html`/`hf`/`rm`) | Kode mati (sisa versi lama: Playwright + render.js) |
| B-02 | `dl()` memanggil `claude.use` tanpa cek `window.claude`; di luar claude.ai error ditelan diam-diam | Tombol unduh tidak berfungsi dan tidak memberi tahu → melanggar aturan "jangan membuat tombol yang tidak berfungsi" |
| B-03 | Fungsi `cards()` memasukkan nama/deskripsi gaya ke `innerHTML` **tanpa escape**; gaya dari AI ("Kejutkan aku") ikut masuk | Celah HTML-injection ringan (sumbernya output AI) |
| B-04 | CSS `.btn{font:600 1rem inherit}` — shorthand tidak valid, deklarasi diabaikan browser | Kosmetik |
| B-05 | State tidak disimpan — reload = semua cerita hilang | UX |
| B-06 | Durasi 90 dtk memakai beat "Dampak" yang tidak ada di templat fallback | Fallback ke templat "Inti"; minor |
| B-07 | SRT harus dibuat manual di alat lain | Titik paling rapuh alurnya — **ZOI bisa menggantinya: Piper TTS + faster-whisper word timestamps → SRT per kata otomatis, lokal, gratis** |

### 3.5 Kesimpulan
Blueprint Studio adalah **generator brief/prompt**, bukan mesin render. Mudah diintegrasikan karena tidak punya backend: ZOI cukup menyiapkan data yang sama (topik, beat, gaya, SRT) lalu (a) mengisinya ke Blueprint Studio, atau (b) memakai template prompt yang sama dengan LLM lokal dan merender lewat HyperFrames secara lokal. Ketergantungan pada `claude.use("sample")` harus diganti/ditambah **provider Ollama** agar sesuai aturan ZERO SUBSCRIPTION — tanpa menghapus jalur claude.ai yang sudah berfungsi.

---

## 4. Fitur ZOI yang diminta — kelayakan gratis

| Fitur | Kelayakan gratis | Klasifikasi |
|---|---|---|
| Avatar 3D + lip-sync | Ya (talking-avatar MIT, Three.js, R3F) | FREE LOCAL |
| Chat AI | Ya (Ollama + model open-weight) | FREE LOCAL |
| Voice input | Ya (faster-whisper) | FREE LOCAL |
| Voice output | Ya (Piper, GPL-3.0) | FREE LOCAL |
| Agent + tools | Ya (Ollama tool calling: Qwen3, Gemma 4) | FREE LOCAL |
| Channel Analytics | Ya (YouTube Data + Analytics API, OAuth) | FREE WITH LIMITS |
| Competitor Intelligence | Ya, data publik saja | FREE WITH LIMITS |
| Viral Video Hunter | Ya, berbasis snapshot berkala | FREE WITH LIMITS (kuota search 100 panggilan/hari) |
| Trend Detector | **Terbatas** — tidak ada API tren resmi yang gratis & terbuka | FREE WITH LIMITS (dari snapshot sendiri) |
| Content Gap / Ide / Naskah / Storyboard | Ya (LLM lokal) | FREE LOCAL |
| Best Upload Time | Hanya jika data Analytics channel tersedia | FREE WITH LIMITS |
| Retention Analyzer | Hanya channel sendiri via Analytics API | FREE WITH LIMITS |
| Monetization Tracker | Ya (subscriber/watch hours via API; revenue hanya jika YPP) | FREE WITH LIMITS |
| ZOI AI CLIPPER | Ya (mode ZOI + Ollama provider baru) | FREE LOCAL |
| BLUEPRINT STUDIO | Ya, setelah provider Ollama + render HyperFrames lokal ditambahkan; jalur claude.ai tetap ada sebagai opsi | FREE LOCAL (target) / jalur saat ini memakai kuota Claude |
| Memory, Task Manager, Automation | Ya (SQLite, APScheduler) | FREE LOCAL |
