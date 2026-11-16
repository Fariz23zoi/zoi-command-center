# ADR 0002 — Dua mode: development dan local

**Status:** diterima (14 Nov 2026)

**Konteks.** Aplikasi dibangun di workspace pengembangan (tanpa bergantung pada hardware laptop), lalu
dipindahkan ke local server Windows tanpa dibangun ulang.

**Keputusan.** Satu variabel `ZOI_MODE` menentukan semua perilaku turunan di satu tempat
(`backend/app/config/modes.py`): penyedia AI, port (8000 / 80), folder data, CORS, penyajian frontend, banner.
Konfigurasi hanya dari environment variable; nama `ZOI_*` yang tidak dikenal ditolak. Phase 1 hanya
mengizinkan bind ke loopback.

**Akibat.** Pindah ke local server = salin paket rilis + isi `.env` + impor data. Tidak ada kode yang berubah.
