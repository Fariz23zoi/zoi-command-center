# Deploy ZOI Online (Render + Neon) — GRATIS, tanpa kartu kredit

Panduan ini memasang ZOI di internet sehingga bisa dibuka dari HP tanpa laptop menyala.
Produksi konten (render video, narasi, CLIPPER, Blueprint Studio) tetap di laptop.

**ATURAN:** semua langkah memakai paket gratis. **Jika Render atau Neon meminta kartu kredit atau
pembayaran pada langkah mana pun — BERHENTI** dan jangan lanjutkan; laporkan di chat.

> Penting: yang ZOI butuhkan dari Neon adalah **connection string** (teks berawalan `postgresql://`),
> **bukan** "API key" Neon. Connection string berisi kata sandi database — **jangan pernah menempelkannya
> di chat, di GitHub, atau di file mana pun**. Ia hanya diisi di layar Environment milik Render.

## 1. Neon — database (sekali saja)

1. Buka https://neon.tech dan masuk ke akunmu.
2. Buat project baru (nama bebas, misal `zoi`). Region: **Singapore (ap-southeast-1)** bila tersedia.
3. Di halaman project, cari panel **Connection Details** / tombol **Connect**.
4. Pilih database `neondb` (bawaan) dan **matikan opsi "Pooled connection"** bila ada pilihannya
   (ZOI memakai koneksi langsung).
5. Salin **connection string** yang berawalan `postgresql://...`. Simpan sementara di tempat aman
   (misal aplikasi catatan pribadi) — akan dipakai di langkah 2 dan bisa dihapus setelahnya.

## 2. Render — aplikasi web

1. Buka https://render.com dan buat akun **dengan tombol "Sign in with GitHub"** (tanpa kartu).
2. Klik **New +** → **Web Service**.
3. Pilih **Build and deploy from a Git repository** → **Connect** pada repo `Fariz23zoi/zoi-command-center`.
   (Bila repo tidak terlihat: klik **Configure account**, beri Render akses ke repo itu.)
4. Isi formulir:
   - **Name**: `zoi` (alamatmu menjadi `https://zoi-XXXX.onrender.com`)
   - **Region**: `Singapore (Southeast Asia)`
   - **Branch**: branch rilis (lihat catatan di bawah)
   - **Runtime/Language**: `Docker` (terdeteksi otomatis dari `Dockerfile`)
   - **Instance Type / Plan**: **Free**
5. Di bagian **Environment Variables**, tambahkan:
   | Nama | Nilai |
   |---|---|
   | `ZOI_MODE` | `online` |
   | `ZOI_DATABASE_URL` | tempel connection string Neon dari langkah 1 |
   | `ZOI_SECRET_KEY` | klik **Generate** (atau isi teks acak ≥ 32 karakter) |
   | `ZOI_SETUP_TOKEN` | klik **Generate** (atau isi teks acak ≥ 16 karakter) |
   | `ZOI_AI_PROVIDER` | `nvidia` |
   | `ZOI_AI_FALLBACK` | `openrouter` |
   | `ZOI_NVIDIA_MODEL` | nama model NVIDIA NIM pilihanmu (boleh dikosongkan dulu) |
   | `ZOI_OPENROUTER_MODEL` | model OpenRouter **gratis**, wajib berakhiran `:free` (boleh kosong dulu) |
6. Klik **Deploy Web Service** dan tunggu sampai status **Live** (build pertama ±10–15 menit).

## 3. Buat kata sandi login (sekali saja)

1. Di halaman service Render, buka tab **Environment** dan **salin nilai `ZOI_SETUP_TOKEN`**.
2. Buka alamat ZOI-mu (`https://zoi-XXXX.onrender.com`). Halaman **Setup** muncul.
3. Tempel setup token, buat kata sandi (minimal 8 karakter), klik **Buat kata sandi**.
4. Selesai — selanjutnya cukup masuk dengan kata sandi itu. Mengganti kata sandi memakai
   setup token yang sama (semua sesi lama otomatis keluar).

## 4. Masukkan API key AI (dari HP juga bisa)

1. Buka **Settings › AI Cloud** di ZOI.
2. Masukkan API key NVIDIA (`nvapi-...`) dan OpenRouter (`sk-or-...`).
   Key disimpan **terenkripsi di database** — tidak pernah di repo atau file.
3. Isi `ZOI_NVIDIA_MODEL` / `ZOI_OPENROUTER_MODEL` di Environment Render (lihat daftar model di
   halaman AI Cloud), lalu **Save, rebuild** bila Render memintanya.

## Keterbatasan paket gratis (normal, bukan kerusakan)

- **Tidur setelah ±15 menit sepi** — permintaan pertama sesudahnya menunggu ±1 menit. Selagi tab ZOI
  terbuka, ZOI mengirim detak otomatis agar tidak tertidur di tengah pemakaian.
- **Jam gratis 750 jam/bulan** — cukup untuk satu service yang kadang tidur.
- **Neon gratis** — database tidur ±5 menit tanpa kueri, bangun dalam ratusan milidetik; penyimpanan
  ±0,5 GB (lebih dari cukup untuk ZOI).
- **Fitur "hanya di laptop"**: AI lokal (Ollama), suara (Whisper/Piper), CLIPPER, Blueprint Studio.
  Halaman-halamannya tetap ada dan menjelaskan hal ini dengan jujur.

## 5. Hubungkan YouTube (opsional)

1. Buka https://console.cloud.google.com → pilih/buat project → **APIs & Services › Library** → aktifkan
   **YouTube Data API v3** dan **YouTube Analytics API** (gratis, berkuota harian).
2. **APIs & Services › OAuth consent screen**: tipe **External**, isi nama aplikasi & email, tambahkan
   scope `youtube.readonly` dan `yt-analytics.readonly`. Status publikasi boleh **In production** tanpa
   verifikasi (hanya kamu yang memakai; Google menampilkan peringatan "aplikasi belum diverifikasi" — klik
   **Advanced › Go to …** untuk lanjut).
3. **APIs & Services › Credentials › Create credentials › OAuth client ID** → tipe **Web application**.
   Pada **Authorized redirect URIs** isi persis alamat yang tertulis di ZOI **Settings › YouTube**
   (bentuknya `https://zoi-XXXX.onrender.com/api/youtube/callback`).
4. Klik **Download JSON**, lalu di ZOI **Settings › YouTube** pilih file itu → **Hubungkan akun YouTube**.
   File dan token disimpan terenkripsi di database. ZOI hanya meminta izin **baca**.

## 6. Cadangan data

**Settings › Cadangan data › Unduh cadangan** menghasilkan satu file `.zip` (chat, memori, tugas, draf,
data YouTube). API key, akun YouTube, dan kata sandi **tidak pernah** ikut. Unduh berkala — layanan gratis
bisa berubah sepihak. Pulihkan dari file yang sama di ZOI versi yang sama (online atau laptop).
