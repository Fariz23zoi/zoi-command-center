# ADR 0004 — Data portabel dalam satu folder

**Status:** diterima (14 Nov 2026)

**Keputusan.**
- Semua data di `ZOI_DATA_DIR`: `zoi.db` (SQLite WAL), `logs/`, `backups/`, `exports/`, dan file data lain.
- Tidak ada path absolut mesin di database. Path relatif terhadap `ZOI_DATA_DIR`; path mesin hanya di `.env`.
  Hasil "Pemeriksaan sistem" disanitasi sebelum disimpan. `doctor` dan tes memindai pelanggaran.
- Waktu disimpan sebagai ISO-8601 UTC.
- `zoi-cli data export` membuat ZIP: `manifest.json` (format, versi, revisi skema, jumlah baris, SHA-256),
  `zoi.db` (salinan konsisten via SQLite backup API — aman walau file sedang dibuka di Windows), `files/`.
- `zoi-cli data import` memverifikasi checksum, menolak path tidak aman dan skema yang lebih baru, mem-backup
  data lama, lalu menjalankan migrasi.
- Migrasi Alembic selalu membuat backup dulu; backup dirotasi (7 terakhir).
