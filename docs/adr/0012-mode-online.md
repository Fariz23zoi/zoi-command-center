# ADR 0012 — Mode online (Render + Neon), login satu kata sandi, rahasia terenkripsi di database

Tanggal: 16 November 2026 · Status: diterima

## Konteks

Keputusan pengguna (15 Nov 2026): ZOI berjalan online — bisa dibuka dari HP tanpa laptop menyala — kecuali
produksi konten (render video, narasi, CLIPPER, Blueprint Studio) yang tetap di laptop. Aturan ZERO PAID /
ZERO SUBSCRIPTION tetap berlaku: hosting dan database harus paket gratis tanpa kartu kredit; bila ada layanan
yang meminta pembayaran, proses berhenti dan dilaporkan.

## Keputusan

1. **Mode ketiga `online`** di samping development/local. Host dipaksa `0.0.0.0`, port dari `$PORT` (Render),
   STT/TTS dimatikan (Whisper/Piper tidak muat dan tidak relevan di server), provider AI hanya
   nvidia/openrouter/none. Model cloud yang belum diisi kini **peringatan**, bukan galat — aplikasi harus tetap
   bisa start di Render sebelum pengguna memilih model.
2. **Database Postgres (Neon)** lewat `ZOI_DATABASE_URL` — wajib di mode online, karena filesystem Render
   ephemeral. Penghubung `pg8000` (BSD, murni Python), TLS wajib ke host non-loopback, `pool_pre_ping` karena
   Neon tertidur (scale-to-zero) dan bangun dalam ratusan milidetik. Pencarian memori memakai full-text
   Postgres (`to_tsvector('simple')` + GIN) menggantikan FTS5 SQLite; migrasi 0003 sadar-dialek.
3. **Login satu kata sandi** (keputusan pengguna). Hash scrypt di `app_meta`; sesi 30 hari sebagai hash SHA-256
   token di tabel `auth_sessions`; cookie `zoi_session` HttpOnly+Secure+SameSite=Lax. Setup/reset kata sandi
   butuh `ZOI_SETUP_TOKEN` dari environment Render. Pembatas global 10 percobaan gagal / 15 menit (pengguna
   tunggal — pembatas per-IP justru bisa diakali). Semua `/api/*` butuh sesi kecuali `/api/health` (health
   check Render) dan `/api/auth/*`; WebSocket memeriksa cookie yang sama. Mode development/local: auth
   nonaktif, perilaku lama tidak berubah.
4. **Rahasia di database, terenkripsi** (`DbSecretStore`): API key NVIDIA/OpenRouter dan token YouTube
   disimpan sebagai token Fernet; kuncinya diturunkan (scrypt) dari `ZOI_SECRET_KEY` yang dibuat Render.
   Antarmuka sama dengan `SecretStore` keyring/file, jadi layanan lain tidak berubah.
5. **Deploy**: `Dockerfile` multi-stage (build frontend Node 22 → image Python 3.12 slim) + `render.yaml`
   (plan free, Singapura, health check `/api/health`). `ZOI_DATABASE_URL` diisi manual di Render — connection
   string Neon tidak pernah masuk repo atau chat.

## Konsekuensi

- Fitur yang butuh laptop (AI lokal Ollama, suara, CLIPPER, Blueprint) di mode online dilaporkan jujur
  "hanya di laptop" — tidak disembunyikan, tidak dipalsukan.
- Hubungkan YouTube memakai alur OAuth web (lihat Tambahan Bagian B).
- Render free tertidur setelah 15 menit tanpa lalu lintas masuk; frontend mengirim detak WebSocket berkala
  selagi tab terbuka agar sesi aktif tidak terputus. Saat benar-benar tidur, permintaan pertama menunggu
  ±1 menit — keterbatasan paket gratis, ditulis di panduan deploy.
- Backup berbasis file SQLite tidak berlaku di Postgres; unduh/pulihkan data dari Settings menyusul di
  Bagian B. Sampai saat itu, data online bersandar pada retensi Neon.

## Tambahan Bagian B (16 November 2026)

- **YouTube di mode online** memakai OAuth client bertipe *Web application* (PKCE + state, 5 menit) dengan
  redirect `https://<alamat publik>/api/youtube/callback`. Callback dilindungi sesi login (cookie ikut karena
  navigasi top-level, SameSite=Lax); galat ditampilkan di Settings › YouTube. File client dan token disimpan
  terenkripsi di tabel `secrets`. Mode local tetap memakai *Desktop app* + loopback.
- **Cadangan `zoi.backup/v2`**: ZIP berisi manifest (revisi skema, jumlah baris, SHA-256 per file) + JSON per
  tabel; bekerja di SQLite dan Postgres. Tidak pernah membawa `secrets`, `auth_sessions`, atau baris
  `app_meta` berawalan `auth:` (hash kata sandi). Pulih = satu transaksi; checksum, revisi skema, dan jumlah
  baris diverifikasi; arsip versi lain ditolak dengan pesan jujur.
- **Paket produksi `zoi.paket/v1`** dari naskah: `beats [{k, n, v}]` — bentuk yang sama dengan struktur cerita
  Blueprint Studio — plus `naskah_tts`, rasio, durasi. Draf mock ditandai `mock: true`.
