# Migrasi ZOI ke local server Windows

Target: ZOI berjalan di `http://127.0.0.1` pada komputer Windows 10/11, memakai Ollama lokal.
Tidak ada biaya layanan. Tidak ada langkah yang mengubah ZOI AI CLIPPER atau Blueprint Studio.

## 0. Yang dibutuhkan

| Kebutuhan | Keterangan |
|---|---|
| Windows 10/11 64-bit | |
| Python 3.12+ | python.org, centang "Add python.exe to PATH" |
| Ruang disk | ±0,3 GB untuk ZOI + cadangan 5 GB untuk Windows (diperiksa otomatis oleh `install.ps1`) |
| Ollama + 1 model lokal | **Opsional dan atas keputusanmu sendiri** — lihat langkah 5. Tanpa ini fitur AI berstatus "tidak tersedia" |
| Node.js | **Tidak perlu** — paket rilis sudah berisi frontend hasil build |

## 1. Siapkan paket

Di workspace pengembangan:

```bash
scripts/build_frontend.sh
backend/.venv/bin/python scripts/build_release.py   # → release/zoi-command-center-<versi>.zip
```

Salin ZIP ke local server dan ekstrak, misalnya ke `C:\ZOI\zoi-command-center`.

## 2. Ekspor data dari mesin lama (jika ada)

```bash
cd backend && python -m app.cli data export --exclude-mock --out zoi-pindah.zip
```

`--exclude-mock` membuang percakapan mock dari mode development agar tidak tercampur data asli.

## 3. Pasang

```powershell
cd C:\ZOI\zoi-command-center
powershell -ExecutionPolicy Bypass -File deploy\windows\install.ps1
```

Skrip memeriksa Python dan ruang disk **sebelum** memasang apa pun, lalu meminta persetujuan sebelum
mengunduh paket Python (±80 MB).

## 4. Isi `.env`

`install.ps1` membuat `.env` dari `.env.local.example`. Sesuaikan:

```ini
ZOI_MODE=local
ZOI_PORT=80
ZOI_OLLAMA_MODEL=          # isi setelah langkah 5
ZOI_CLIPPER_DIR=C:\ZOI\zoi-ai-clipper
ZOI_BLUEPRINT_FILE=C:\ZOI\blueprint-studio\Blueprint_Studio.html
```

Jika port 80 dipakai program lain (IIS, XAMPP, dll.), `doctor` menyebut programnya. ZOI tidak mematikan
program lain — pilih: hentikan program itu, atau set `ZOI_PORT=8000` (alamat menjadi `http://127.0.0.1:8000`).

## 5. (Opsional) Ollama dan model lokal

ZOI **tidak pernah** memasang Ollama atau mengunduh model. Bila hardware memadai (lihat
`docs/audit/HARDWARE_REQUIREMENTS.md`) dan kamu setuju dengan ukuran unduhannya:

1. Pasang Ollama dari ollama.com/download (gratis, open source). Bila disk C: sempit, atur `OLLAMA_MODELS`
   ke drive lain sebelum mengunduh model.
2. Unduh satu model lokal, misalnya `ollama pull qwen3:4b` (±2,5 GB) atau `qwen3:8b` (±5 GB).
   Jangan memakai model bertag `cloud` — ZOI menolaknya.
3. Isi `ZOI_OLLAMA_MODEL` di `.env` — atau pilih model nanti di **Settings › AI Lokal** (pilihan di sana
   tersimpan di database dan menimpa `.env`).

Ollama di komputer lain di jaringan rumah juga bisa: `ZOI_OLLAMA_URL=http://192.168.x.x:11434` dan tambahkan
`192.168.x.x` ke `ZOI_EXTRA_ALLOWED_HOSTS`.

## 5b. (Opsional) Suara

ZOI **tidak pernah** mengunduh model suara. Tanpa langkah ini ZOI tetap bisa membacakan jawaban dengan suara
lokal Windows (Settings Windows › Time & language › Language & region › Bahasa Indonesia, fitur Text-to-speech).

1. Pengenal suara (bicara ke ZOI):
   ```powershell
   backend\.venv\Scripts\pip install -r backend\requirements-voice.txt
   backend\.venv\Scripts\python -c "from faster_whisper import download_model; download_model('base', output_dir=r'D:\zoi-models\whisper-base')"
   ```
   Isi `.env`: `ZOI_WHISPER_MODEL_DIR=D:\zoi-models\whisper-base`. Di laptop lemah mulai dari `tiny` (±75 MB).
2. Suara Piper (lip-sync avatar 3D) — **baca catatan lisensinya di Settings › Suara dulu**:
   ```powershell
   python -m venv C:\zoi-piper
   C:\zoi-piper\Scripts\pip install "piper-tts[http]==1.8.0"
   C:\zoi-piper\Scripts\python -m piper.download_voices --data-dir D:\zoi-models\piper id_ID-news_tts-medium
   powershell -ExecutionPolicy Bypass -File deploy\windows\voice.ps1
   ```

## 5c. (Opsional) YouTube — channel-mu sendiri

Gratis (kuota harian), tanpa kartu kredit. ZOI hanya **membaca**; tidak bisa mengunggah atau mengubah apa pun.

1. Buka <https://console.cloud.google.com> → buat project (mis. "ZOI"). **Jangan** aktifkan billing.
2. *APIs & Services › Library* → aktifkan **YouTube Data API v3** dan **YouTube Analytics API**.
3. *Google Auth Platform* (layar izin OAuth): tipe **External**; isi nama aplikasi dan emailmu;
   di *Data Access* tambahkan scope `youtube.readonly` dan `yt-analytics.readonly`;
   di *Audience* tekan **Publish app** agar status menjadi **In production** (status *Testing* membuat izin
   kedaluwarsa tiap 7 hari). Verifikasi Google tidak diperlukan untuk pemakaian pribadi.
4. *Clients › Create client* → tipe **Desktop app** → **Download JSON**.
5. Simpan file itu di komputer ini saja. **Jangan** kirim ke chat, email, atau GitHub.
6. Di ZOI: *Settings › YouTube* → pilih file itu → **Hubungkan akun YouTube** → login di tab Google.
   Google menampilkan "Google hasn't verified this app" → *Advanced* → *Go to … (unsafe)* — ini wajar untuk
   aplikasi buatan sendiri. Centang **kedua** izin, lalu kembali ke tab ZOI.

Nama menu di Google Cloud bisa berubah; bila berbeda, cari padanannya. Bila ada langkah yang meminta pembayaran,
berhenti dan laporkan — tidak ada bagian ZOI yang memerlukannya.

## 5d. (Opsional) AI cloud gratis — NVIDIA NIM, cadangan OpenRouter

Bawaan ZOI tetap lokal. Langkah ini membuat chat, agen, ide, dan naskah dijawab server NVIDIA/OpenRouter, sehingga
**isi chat, memori, judul video, dan naskahmu dikirim ke sana**. Rekaman suara, token YouTube, dan API key tidak.

1. Daftar di <https://build.nvidia.com> → buat API key (`nvapi-…`). Baca ketentuan uji cobanya dulu.
2. (Cadangan) Daftar di <https://openrouter.ai> → buat API key (`sk-or-…`). **Jangan membeli kredit.** Periksa
   pengaturan privasinya.
3. Tambahkan ke file `.env`, lalu jalankan ulang ZOI:
   ```
   ZOI_AI_PROVIDER=nvidia
   ZOI_NVIDIA_MODEL=<nama model dari build.nvidia.com>
   ZOI_AI_FALLBACK=openrouter
   ZOI_OPENROUTER_MODEL=<model gratis, harus berakhiran :free>
   ```
   Tanpa cadangan: hapus dua baris terakhir.
4. Buka *Settings › AI Cloud* → masukkan API key masing-masing → **Uji model**. Bila gagal dengan "tidak bisa
   memanggil model", pilih nama lain dari **Lihat daftar model**, ubah `.env`, jalankan ulang.
5. **Jangan** menaruh API key di `.env`, chat, atau GitHub.

Kembali ke lokal: hapus baris-baris itu dari `.env` dan jalankan ulang.

## 5e. (Opsional) Produksi konten — Blueprint Studio & HyperFrames

1. **Blueprint Studio**: isi `ZOI_BLUEPRINT_FILE` dengan path file `Blueprint_Studio.html` milikmu. Buka
   ZOI › **Content Production** › **Buat salinan**. ZOI menulis salinan di `data/blueprint/` dengan tombol
   **Muat paket ZOI**; file aslimu hanya dibaca. Salinan dibuka di `http://127.0.0.1/blueprint-studio/`.
2. **Paket**: di ZOI (online atau laptop) buka **Script & Storyboard › Unduh paket produksi**, lalu di laptop
   **Content Production › Impor paket**. Tombol **Buka di Blueprint Studio** mengisi topik, durasi, rasio,
   beat, dan SRT narasi secara otomatis.
3. **Narasi** (butuh Piper dari bagian 5b): **Buat narasi** → `narasi.wav` + `narasi.srt` (waktu per beat dari
   audio sungguhan).
4. **HyperFrames** (opsional, berat untuk laptop lemah): pasang Node.js 22+ dari nodejs.org, lalu di folder
   pilihanmu jalankan `npm install hyperframes`. Isi `ZOI_HYPERFRAMES_DIR` dengan folder itu. ZOI memakai
   Chrome/Edge yang sudah terpasang (tidak mengunduh browser) dan mematikan telemetri HyperFrames. Hasil:
   kartu teks beranimasi + narasi sebagai `video.mp4` — bukan pengganti animasi Blueprint + Claude.

## 6. Impor data (jika ada)

```powershell
cd backend
..\backend\.venv\Scripts\python.exe -m app.cli data import ..\zoi-pindah.zip
```

ZOI harus dalam keadaan berhenti. Data lama di-backup otomatis ke `data\backups\`.

## 7. Jalankan dan periksa

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\start.ps1 -OpenBrowser
```

Buka `http://127.0.0.1` lalu:

- [ ] Tidak ada pita kuning "DEVELOPMENT MODE"
- [ ] Status "Tersambung" di bilah atas
- [ ] Pill AI menampilkan nama model (atau "tidak tersedia" dengan alasan yang jelas bila Ollama belum ada)
- [ ] Task Manager → "Jalankan pemeriksaan sistem" → Selesai
- [ ] Overview menampilkan CLIPPER/Blueprint "ditemukan (read-only)" bila path diisi
- [ ] `python -m app.cli doctor --skip-port` tanpa baris FAIL
- [ ] (Bila Ollama dipasang) Settings › AI Lokal: versi Ollama, model terpasang, dan model aktif tampil;
      "Uji koneksi" berhasil; chat menjawab tanpa lencana MOCK; tombol **Berhenti** menghentikan jawaban
- [ ] (Bila Ollama dipasang) Jalankan **Uji model** sekali untuk model aktif dan nilai jawaban percakapannya.
      Ini pertama kalinya ZOI berbicara dengan Ollama sungguhan — semua tes sebelumnya memakai Ollama tiruan
- [ ] (Bila suara dipasang) Settings › Suara: pengenal suara "siap"; tekan 🎙, ucapkan satu kalimat Bahasa Indonesia,
      tekan Selesai → teks masuk kotak pesan. Ini pertama kalinya Whisper dijalankan dengan model sungguhan
- [ ] (Bila Piper dipasang) Terima catatan lisensi → "Coba suara" → avatar bicara; nyalakan "Bacakan jawaban" dan
      uji tombol Berhenti
- [ ] (Bila Ollama dipasang) Ketik permintaan lalu tekan **Rencanakan** (mis. "cek status sistem lalu catat hasilnya
      di memori") → periksa rencana → Jalankan → setujui langkah simpan memori. Ini pertama kalinya perencana
      memakai model sungguhan; bila rencananya buruk, jalankan **Uji model** dan lihat skor tool
- [ ] Halaman Memory: tambah satu memori, cari, ubah, hapus
- [ ] (Bila YouTube disiapkan) Settings › YouTube: **tidak ada** pita "ENDPOINT UJI"; "Penyimpanan token" menyebut
      Windows Credential Manager (bukan peringatan file biasa). Hubungkan akun → nama channel-mu tampil.
      Ini pertama kalinya ZOI berbicara dengan Google sungguhan — semua tes sebelumnya memakai Google tiruan
- [ ] (Bila YouTube disiapkan) Channel Analytics → "Ambil data terbaru" → bandingkan subscriber, total tayangan,
      dan tayangan 28 hari dengan YouTube Studio. Laporkan bila ada angka yang berbeda atau pesan error
- [ ] (Bila YouTube disiapkan) Competitor Intelligence: tambah satu channel lewat handle → nama dan angkanya cocok
      dengan halaman channel itu di YouTube. Viral Video Hunter → "Ambil Trending" → bandingkan beberapa judul
      teratas dengan youtube.com/feed/trending (urutan bisa sedikit berbeda antara API dan situs)
- [ ] (Bila YouTube + Ollama) Trend Detector → "Rangkum tema" pada daftar Trending. Ini pertama kalinya rangkuman
      dibuat model sungguhan: periksa apakah temanya masuk akal dan berapa contoh yang dibuang
- [ ] (Bila Ollama dipasang) Content Ideas → minta 3 ide → "Tulis naskah dari ide ini". Catat berapa lama tiap
      tugas berjalan di laptop ini (batasnya 15 menit) dan apakah naskahnya layak dipakai sebagai draf
- [ ] (Bila AI cloud diaktifkan) Settings › AI Cloud: **tidak ada** pita "ENDPOINT UJI"; "Uji model" NVIDIA
      menjawab. Ini pertama kalinya ZOI berbicara dengan NVIDIA sungguhan. Kirim satu pesan di AI Assistant →
      jawabannya berlabel "AI cloud · NVIDIA NIM · <model>". Laporkan pesan error apa pun apa adanya
- [ ] (Bila cadangan diaktifkan) "Uji model" OpenRouter menjawab. Hitungan "permintaan hari ini" bertambah satu
- [ ] (Bila AI cloud diaktifkan) Minta agen satu rencana sederhana dan satu set ide konten; catat apakah model
      yang dipilih sanggup (keluaran JSON dan pemanggilan tool berbeda-beda antar-model)
- [ ] (Bila YouTube disiapkan) Buka *Control Panel › Credential Manager › Windows Credentials* → ada entri
      `zoi-youtube-intelligence`. Folder `data\secrets` hanya berisi `youtube_client.json`
- [ ] (Opsional) Jalankan tes roundtrip suara: `ZOI_TEST_WHISPER_DIR=… ZOI_TEST_PIPER_URL=http://127.0.0.1:5000
      python -m pytest tests/test_voice.py -k real`

Opsional: `deploy\windows\autostart.ps1` agar ZOI berjalan otomatis saat login.

## Catatan jujur

- Skrip PowerShell belum pernah dijalankan di Windows sungguhan (lingkungan pengembangan tidak memiliki
  PowerShell). Laporkan baris error apa pun saat migrasi; perbaikan dilakukan sebelum Phase 2 dianggap selesai.
- Kode backend dan frontend sudah diuji otomatis di Linux, termasuk E2E dalam mode local pada satu port.
- AI cloud (NVIDIA NIM, OpenRouter) diuji terhadap server **tiruan** bergaya OpenAI; belum pernah dipanggil sungguhan.
- Integrasi YouTube diuji terhadap server Google **tiruan**. Bentuk respons mengikuti dokumentasi resmi, tetapi
  belum pernah dibandingkan dengan respons Google sungguhan, dan `keyring` belum pernah dijalankan di Windows.
