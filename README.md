# ZOI — Command Center (YouTube Intelligence)

Platform web lokal dengan avatar ZOI sebagai pusat kendali ekosistem YouTube.
**ZERO PAID API · ZERO SUBSCRIPTION · LOCAL FIRST.** Lisensi: MIT.

> Status: **Phase 1 — fondasi.** Lihat tabel "Yang sudah berfungsi" di bawah. Fitur yang belum dibangun
> ditampilkan sebagai "Belum tersedia — Phase N", tanpa data contoh.

## Arsitektur singkat

| Bagian | Lokasi | Catatan |
|---|---|---|
| Frontend | `frontend/apps/web` | React + TypeScript + Vite. Di mode local disajikan backend sebagai file statis |
| Avatar | `frontend/packages/avatar` | Paket terpisah. Sekarang avatar 2D (SVG); 3D menyusul di Phase 2 tanpa mengubah aplikasi |
| Backend | `backend/app` | FastAPI, satu proses, bind `127.0.0.1` saja |
| Database | `backend/app/db` | SQLite satu file di `ZOI_DATA_DIR`, migrasi Alembic, ekspor/impor ZIP berverifikasi |
| Penyedia AI | `backend/app/providers` | `mock` (development, selalu berlabel MOCK) · `ollama` (local) · `none` |
| Integrasi | `backend/app/integrations` | Adapter ZOI AI CLIPPER & Blueprint Studio — **read-only**, aplikasi asli tidak diubah |

## Dua mode

| | `ZOI_MODE=development` | `ZOI_MODE=local` |
|---|---|---|
| Penyedia AI | Mock (jawaban berlabel **MOCK**, tidak pernah membuat statistik) | Ollama lokal; **mock ditolak** |
| Alamat | Vite `http://127.0.0.1:5173` → backend `:8000` | Satu alamat: `http://127.0.0.1` (port 80) |
| Banner | Pita kuning "DEVELOPMENT MODE" | Tidak ada |

Semua konfigurasi lewat environment variable / file `.env` — lihat `.env.development.example` dan
`.env.local.example`. Nama variabel yang salah ketik ditolak saat start.

## Menjalankan

**Development** (workspace pengembangan, butuh Python 3.12+ dan Node 22.12+):

```bash
cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && cd ..
cd frontend && npm ci && cd ..
scripts/dev.sh            # buka http://127.0.0.1:5173
```

**Local server Windows**: pakai paket rilis (frontend sudah di-build, tanpa Node.js) dan ikuti
[`docs/MIGRATION_TO_LOCAL_SERVER.md`](docs/MIGRATION_TO_LOCAL_SERVER.md).

## Alat baris perintah

```bash
cd backend
python -m app.cli doctor                         # cek Python, disk, port, frontend, Ollama, path, portabilitas
python -m app.cli data export --exclude-mock     # satu file ZIP berisi semua data + checksum
python -m app.cli data import <file.zip>         # pulihkan (ZOI harus berhenti; data lama di-backup dulu)
python -m app.cli db upgrade | db status | backup
```

## Yang sudah berfungsi (Phase 1)

| Fitur | Status |
|---|---|
| Layout command center 5 zona, 16 menu, responsif 375–1440 px | ✅ |
| Avatar 2D mengikuti 12 status nyata dari backend | ✅ |
| Chat minimal (Mock di development, Ollama di local) dengan streaming | ✅ |
| Task Manager: progress langsung, riwayat, pembatalan; tugas nyata "Pemeriksaan sistem" | ✅ |
| Status sistem, penyedia AI, dan deteksi CLIPPER/Blueprint (read-only) | ✅ |
| Cost Guard: koneksi keluar hanya ke allowlist; layanan AI berbayar diblokir & dicatat | ✅ |
| Ekspor/impor data portabel + backup otomatis sebelum migrasi | ✅ |
| YouTube, ide konten, CLIPPER/Blueprint penuh, memory, automation, voice, avatar 3D | Phase 2–8 |

## Pengujian

```bash
cd backend && .venv/bin/python -m pytest          # backend
cd frontend && npm run lint && npm run typecheck && npm test
cd frontend && E2E_CHROME=/path/ke/chrome npx playwright test   # E2E development + local
backend/.venv/bin/python scripts/check_licenses.py              # lisensi semua dependensi
```

## Dokumen

- `docs/audit/` — audit Phase 0 dan rencana Phase 1
- `docs/adr/` — keputusan arsitektur
- `THIRD_PARTY_NOTICES.md` — lisensi dependensi (dibuat otomatis)
