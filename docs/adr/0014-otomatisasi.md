# ADR 0014 — Otomatisasi terjadwal, susulan, pembangun GitHub Actions, notifikasi di dalam ZOI

Tanggal: 16 November 2026 · Status: diterima

## Konteks
Phase 8 meminta laporan harian/mingguan, pemantauan tren & kompetitor, pengingat produksi, dan pelacakan
monetisasi. ZOI online berjalan di Render free yang tertidur saat sepi. Keputusan pengguna: jadwal
**dibangunkan GitHub Actions**; hasil **hanya di dalam ZOI**.

## Keputusan
1. Empat jenis: laporan channel (angka YouTube apa adanya + nilai sebelumnya + syarat YPP, tanpa selisih,
   persentase, atau prediksi), pantau kompetitor (video baru = fakta), pantau Trending ID (judul baru = fakta),
   pengingat produksi (teks pengguna). Tanpa AI — tidak ada angka yang dikarang.
2. Jadwal harian/mingguan dalam WIB (`zoneinfo`). Penjadwal di dalam proses memeriksa tiap 60 detik selagi
   bangun. Jadwal yang terlewat dijalankan **sekali** (tidak menumpuk) dan diberi label "susulan/terlambat"
   bila lewat > 10 menit.
3. Tiap jalan = tugas Task Manager jalur `automation` (bisa dibatalkan). Riwayat 60 jalan terakhir per
   otomatisasi; notifikasi maksimal 300. Jalan yang tertinggal saat server dimulai ulang ditandai "Terputus"
   dan tidak diulang diam-diam.
4. `POST /api/automation/wake` dengan `ZOI_WAKE_TOKEN` (Bearer, ≥ 24 karakter, perbandingan waktu-konstan),
   dikecualikan dari sesi login, hanya memicu pemeriksaan jadwal. Nonaktif bila token kosong.
5. `.github/workflows/zoi-wake.yml`: tiga kali sehari + tombol manual, `permissions: {}`, alamat dan token
   dari Secrets, percobaan ulang selama Render bangun.
6. Kegagalan (akun belum terhubung, kuota habis) menjadi notifikasi "Otomatisasi gagal" dengan pesan apa adanya.

## Konsekuensi
- Jadwal GitHub bisa terlambat; ada laporan tidak resmi bahwa `schedule` tidak berjalan di repo privat akun
  gratis. Susulan saat bangun tetap menjamin jadwal berjalan paling lambat saat ZOI dibuka; panduan menjelaskan
  alternatif repo publik kecil.
- Pantauan memakai kuota YouTube API (dihitung oleh penjaga kuota yang sudah ada).
- Tidak ada publikasi otomatis, email, atau layanan notifikasi luar.
