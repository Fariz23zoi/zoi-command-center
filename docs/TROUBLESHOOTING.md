# Troubleshooting ZOI

Pesan galat ZOI selalu berbahasa Indonesia dan menjelaskan penyebabnya. Daftar ini untuk masalah yang
paling mungkin muncul. Untuk laptop, jalankan dulu `cd backend && .venv\Scripts\python -m app.cli doctor`.

## ZOI online (Render + Neon)

| Gejala | Penyebab & langkah |
|---|---|
| Halaman lama terbuka (±1 menit) atau "Server belum menjawab" | Render free tertidur setelah ±15 menit sepi. Tunggu lalu **Coba lagi**. Normal. |
| Deploy gagal: `ZOI_DATABASE_URL …` | Connection string Neon salah/kosong. Salin ulang dari Neon › Connect (koneksi langsung, bukan *pooled*), tempel di Render › Environment. |
| Deploy gagal: `ZOI_SECRET_KEY` / `ZOI_SETUP_TOKEN` | Belum diisi atau terlalu pendek. Klik **Generate** di Render. |
| "Setup token tidak cocok" | Salin nilai `ZOI_SETUP_TOKEN` persis dari Render › Environment (tanpa spasi). |
| "Terlalu banyak percobaan gagal" | Tunggu 15 menit, atau buat kata sandi baru lewat halaman setup dengan setup token. |
| API key AI hilang setelah mengganti `ZOI_SECRET_KEY` | Disengaja: rahasia lama tidak bisa dibuka dengan kunci baru. Masukkan ulang di Settings › AI Cloud dan hubungkan ulang YouTube. |
| AI "tidak tersedia" | `ZOI_NVIDIA_MODEL` belum diisi, atau API key belum dimasukkan. Lihat Settings › AI Cloud. |
| Google: "redirect_uri_mismatch" | Authorized redirect URI di Google Cloud harus **persis** sama dengan yang ditulis di Settings › YouTube. |
| Google: "aplikasi belum diverifikasi" | Normal untuk OAuth client pribadi: **Advanced › Go to …**. |
| Halaman Produksi Konten berkata "hanya di laptop" | Disengaja. Unduh paket dari halaman Naskah lalu impor di ZOI laptop. |
| Jadwal tidak jalan tepat waktu | Lihat `DEPLOY_ONLINE.md` bagian 6. Tanpa workflow, jadwal jalan saat ZOI dibuka (label "terlambat"). |
| Workflow "ZOI bangun" gagal HTTP 401 | `ZOI_WAKE_TOKEN` di GitHub Secrets beda dengan di Render. |
| Render/Neon meminta kartu kredit | **Berhenti.** Jangan masukkan kartu (aturan ZERO PAID). Laporkan. |

## ZOI laptop (Windows, mode local)

| Gejala | Penyebab & langkah |
|---|---|
| `start.ps1` berkata port 80 dipakai | Program lain (IIS, XAMPP, Skype lama) memakai port 80. Hentikan program itu atau set `ZOI_PORT=8000`. |
| "Frontend ZOI belum di-build" | Gunakan paket rilis ZIP (sudah berisi frontend), bukan kode dari GitHub langsung. |
| Ollama "tidak terjangkau" | Jalankan aplikasi Ollama; periksa `ZOI_OLLAMA_URL`. |
| Mikrofon mati | `ZOI_WHISPER_MODEL_DIR` belum diisi atau folder model tidak lengkap (lihat panduan migrasi 5b). |
| Suara Piper tidak bicara | Server Piper belum jalan (`voice.ps1`), atau catatan lisensi belum diterima di Settings › Suara. |
| "Struktur file Blueprint Studio tidak dikenali" | `ZOI_BLUEPRINT_FILE` menunjuk file lain atau Blueprint Studio berubah besar. ZOI menolak agar tidak merusak; laporkan versinya. |
| Render HyperFrames: "Chrome atau Edge tidak ditemukan" | Pasang Chrome atau pastikan Edge ada. ZOI tidak membiarkan HyperFrames mengunduh browser sendiri. |
| Render HyperFrames sangat lama | Laptop lemah (1 proses Chrome). Biarkan berjalan atau batalkan dari Task Manager; batas 60 menit. |
| "Database memakai revisi skema … lebih baru" | Data dibuat oleh ZOI versi lebih baru. Perbarui ZOI dulu (panduan migrasi bagian 8). |

## Data & cadangan

- **Unduh cadangan** rutin dari Settings (online dan laptop). Berisi semua data kecuali rahasia.
- Cadangan hanya bisa dipulihkan di ZOI dengan versi skema yang sama; pesan galatnya menjelaskan bila beda.
- Laptop: setiap kenaikan skema membuat salinan database otomatis di `data\backups`.

## Melapor

Sertakan: mode (online/laptop), versi (buka `/api/health` di alamat ZOI), pesan galat persis, dan langkah
terakhir. **Jangan** sertakan API key, connection string, kata sandi, setup token, atau file client OAuth.
