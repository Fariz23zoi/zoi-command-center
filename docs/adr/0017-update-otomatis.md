# ADR 0017 — Update otomatis dari GitHub Releases

Status: diterima (17 Nov 2026) · Versi 1.2.4

## Keputusan pemilik
- Repo `Fariz23zoi/zoi-command-center` dijadikan **publik** agar laptop bisa mengunduh rilis tanpa token.
- **Cek otomatis, pasang satu klik**: tidak ada pemasangan tanpa tombol.

## Rancangan
- `.github/workflows/release.yml`: setiap push ke `main` dengan versi baru (`backend/app/__init__.py`) → scan rahasia,
  build, buat rilis `v<versi>` berisi ZIP + `.sha256`, catatan dari `CHANGELOG.md`. Gratis (Actions repo publik).
- Backend `app/update/`: cek `releases/latest` 2 menit setelah start lalu tiap 24 jam (mode local saja; matikan dengan
  `ZOI_UPDATE_CHECK=false`). Host GitHub masuk allowlist Cost Guard (`UPDATE_HOSTS`).
- Pasang (`POST /api/update/install`, Windows): unduh ZIP & `.sha256` dari rilis yang sama, cocokkan hash, cek isi ZIP
  (tanpa path traversal), ekstrak ke folder saudara `zoi-command-center-<versi>`, jalankan `apply-update.ps1` di jendela
  baru: hentikan ZOI → salin `.env` & data → pasang paket (+ paket suara bila dipakai) → nyalakan versi baru; gagal →
  nyalakan lagi versi lama. Folder lama tidak dihapus. Log: `update.log`.

## Batasan
- Hash melindungi dari file rusak/terpotong, bukan dari akun GitHub yang dibobol (tidak ada tanda tangan kode).
- Pemasangan butuh internet untuk paket Python; perubahan migrasi DB berjalan otomatis saat versi baru start.
