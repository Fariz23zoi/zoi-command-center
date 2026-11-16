# ADR 0007 — Suara: faster-whisper di proses ZOI, Piper sebagai program terpisah, suara Windows sebagai jalur aman

**Status:** diterima (14 Nov 2026). Keputusan pengguna: K-1 "keduanya" (Piper + suara Windows),
K-2 "ZOI tidak mengunduh model suara", K-3 "boleh uji model asli di workspace cloud", K-4 "transkrip masuk kotak
pesan dulu".

**Keputusan.**
- **Pengenal suara:** faster-whisper 1.2.1 (MIT) di proses backend, paket **opsional** (`requirements-voice.txt`),
  diimpor malas. Hanya memuat dari folder `ZOI_WHISPER_MODEL_DIR` dengan `local_files_only=True`, CPU int8, satu
  transkripsi pada satu waktu, VAD bawaan paket (tanpa unduhan). Batas: 10 MB / 60 detik per rekaman.
- **PyAV dikunci ke 18.0.0.** PyAV 19 menghapus argumen `metadata_errors` yang dipakai faster-whisper 1.2.1, sehingga
  semua rekaman gagal didekode. Ditemukan saat implementasi; ada tes yang mendekode WebM/Opus sungguhan.
- **Suara ZOI:** Piper 1.8.0 (GPL-3.0) dijalankan sebagai **program terpisah** (`python -m piper.http_server`,
  `deploy/windows/voice.ps1`). ZOI hanya mengirim teks lewat HTTP lokal (`/voices`, `/synthesize`) dan tidak
  mengimpor kode Piper (dijaga tes). Endpoint Piper yang mengunduh suara (`/download`, `/all-voices`) diblokir di klien.
- **Lisensi suara Indonesia** tidak jelas → `/api/voice/speak` menolak memakai Piper asli sampai catatan lisensi
  diterima di Settings › Suara (`piper_license_accepted`, ikut ekspor).
- **Jalur aman tanpa unduhan:** `speechSynthesis` browser dengan **hanya** suara `localService` (suara Online/Natural
  Edge = cloud, tidak pernah dipakai). Tanpa lip-sync karena browser tidak memberi audionya.
- **Web Speech API (SpeechRecognition) tidak dipakai** — di Chrome audio dikirim ke Google.
- **Alur:** tekan-untuk-bicara (bukan selalu mendengar) → MediaRecorder → `/api/voice/transcribe` (badan mentah,
  tidak disimpan) → teks ke kotak pesan (kirim otomatis opsional). Jawaban dipotong per kalimat; audio kalimat
  berikutnya disiapkan saat kalimat sekarang diputar; avatar 3D memakai `speak(blob)` (lip-sync), 2D memakai
  `<audio>`. "Berhenti" menghentikan suara dan jawaban. Status avatar (LISTENING/THINKING/SPEAKING) selama suara
  adalah status lokal browser, bukan status backend.
- **Development:** MockSTT (transkrip berlabel `[MOCK]`, tanpa angka) dan MockTTS (nada uji, bukan suara manusia).
  Mock suara ditolak di mode local, sama seperti Mock AI.

**Konsekuensi.**
- Uji model sungguhan (K-3) **belum terlaksana**: workspace cloud memblokir huggingface.co. Tes roundtrip
  Piper → Whisper Bahasa Indonesia sudah ditulis (`test_real_roundtrip_piper_to_whisper_in_indonesian`) dan dilewati
  sampai `ZOI_TEST_WHISPER_DIR` + `ZOI_TEST_PIPER_URL` tersedia.
- Akses mikrofon hanya dari `http://127.0.0.1`/`localhost`; dari HP lewat LAN butuh HTTPS (bukan Phase 4).
