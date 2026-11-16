# PHASE1_PLAN.md — Revisi 2: Portable Development → Local Server Deployment

Status: **RENCANA — belum ada kode, belum ada instalasi.** Menggantikan revisi 1.
Tanggal: 14 November 2026.

---

## A. Evaluasi ulang hasil audit Phase 0

| Dokumen | Status setelah keputusan baru | Catatan |
|---|---|---|
| FEATURE_AUDIT.md | ✅ Tetap berlaku | Temuan CLIPPER (C-01…C-10) dan Blueprint (B-01…B-07) tidak berubah; tetap **tidak diperbaiki** tanpa persetujuan |
| GITHUB_REPOSITORY_AUDIT.md | ✅ Tetap berlaku | Klasifikasi repo sama |
| LICENSE_COMPLIANCE.md | ✅ Tetap berlaku | Mock Provider = kode sendiri, tanpa lisensi pihak ketiga |
| COST_CONTROL.md | ✅ Tetap berlaku | Mock Provider = FREE LOCAL. Cost Guard aktif di kedua mode |
| SECURITY_AUDIT.md | ✅ Tetap berlaku | Ditambah: mode LOCAL tidak boleh memakai Mock |
| INTEGRATION_PLAN.md | ✅ Berlaku, dipertegas | Adapter CLIPPER = subprocess dengan path dari environment variable → portabel antar-mesin |
| ARCHITECTURE.md | ✅ Tetap target akhir | Ditambah lapisan *mode* dan Mock Provider |
| HARDWARE_REQUIREMENTS.md (rev. 2) | ⚠️ Berubah peran | Kini hanya menggambarkan **laptop saat ini**. Pengembangan tidak lagi bergantung padanya. Spesifikasi *local server* = edisi **ZOI Standard** (CPU AVX2 4 core, RAM 16 GB, SSD 40 GB kosong) |
| ARCHITECTURE_ZOI_LITE.md | ⚠️ Berubah peran | Menjadi **profil deployment "lite"** (avatar 2D, AI nonaktif) bila aplikasi dijalankan di laptop lemah. Kodenya sama; hanya konfigurasi yang berbeda |
| IMPLEMENTATION_PLAN.md | ⚠️ Disesuaikan | Mock Provider masuk Phase 1; Phase 3 menjadi "Ollama Provider di local server"; ditambah fase akhir "Migrasi ke local server" |
| PHASE1_PLAN.md rev. 1 | ❌ Digantikan dokumen ini | Versi dependensi (diverifikasi 14 Nov 2026) dipakai ulang |

**Kesimpulan:** audit Phase 0 tetap sah. Perubahan terbesar ada pada **di mana** aplikasi dibangun (workspace pengembangan portabel, bukan laptop) dan munculnya **Mock Provider** yang harus dibatasi ketat agar tidak melanggar aturan "tanpa data palsu".

---

## B. Prinsip arsitektur (dari keputusanmu)

1. **Dibangun di workspace pengembangan** (Linux, sesi ini) → kode di GitHub private → nanti di-*deploy* ke local server. Laptop saat ini **tidak menjalankan apa pun** selama Phase 1.
2. **Dua mode** lewat satu environment variable: `ZOI_MODE=development` atau `ZOI_MODE=local`.
3. **Enam bagian terpisah**: frontend · backend · database · AI provider · avatar · integrasi aplikasi. Masing-masing berkomunikasi lewat antarmuka yang jelas, sehingga bisa diganti tanpa menyentuh bagian lain.
4. **Konfigurasi hanya dari environment variable** (`.env`). Path yang khusus milik satu mesin tidak pernah disimpan di database.
5. **Data portabel**: seluruh data ada di satu folder (`ZOI_DATA_DIR`), bisa diekspor/impor sebagai satu file ZIP berverifikasi.
6. ZERO PAID API / SUBSCRIPTION. CLIPPER & Blueprint Studio tidak diubah. Tidak ada model AI yang diunduh, tidak ada proses berat.

---

## C. Sistem konfigurasi minimal

### C.1 Aturan per mode

| Aspek | `development` | `local` |
|---|---|---|
| Provider AI default | **mock** | **ollama** |
| Mock boleh dipakai? | Ya, **dengan label wajib** | **Tidak** — aplikasi menolak start jika `ZOI_AI_PROVIDER=mock` |
| Jika AI tidak tersedia | — | Fitur AI menampilkan "AI tidak tersedia" + alasan. **Tidak pernah diam-diam pindah ke mock atau ke cloud** |
| Frontend | Vite dev server (`127.0.0.1:5173`) dengan proxy ke backend | Hasil build statis **disajikan oleh backend** di satu alamat: `http://127.0.0.1:<ZOI_PORT>` |
| CORS | Hanya `http://127.0.0.1:5173` | Tidak ada (satu origin) |
| Banner UI | Pita kuning tetap: **"DEVELOPMENT MODE — jawaban AI adalah MOCK, bukan AI sungguhan"** | Tidak ada |
| Folder data default | `./data-dev` | `./data` (atau path di `.env`) |
| Data YouTube | Hanya data nyata jika kredensial diisi; jika tidak, "Belum terhubung". **Tidak ada statistik tiruan di UI** | Sama |
| Cost Guard jaringan | Aktif | Aktif |

### C.2 Daftar environment variable (Phase 1)

| Variabel | Default | Keterangan |
|---|---|---|
| `ZOI_MODE` | `development` | `development` \| `local` |
| `ZOI_HOST` | `127.0.0.1` | Bind lokal saja. `0.0.0.0` hanya bila sengaja dibuka ke jaringan rumah (Phase 10, dengan token) |
| `ZOI_PORT` | `8000` (development) · **`80` (local)** — diputuskan 14 Nov 2026 | Mode local: alamat cukup `http://127.0.0.1`. Mode development tetap 8000 karena Vite mem-*proxy* ke sana. Lihat risiko R-4 |
| `ZOI_DATA_DIR` | `./data-dev` / `./data` | Database, log, backup, file media, paket produksi |
| `ZOI_LOG_LEVEL` | `INFO` | |
| `ZOI_AI_PROVIDER` | `auto` | `auto` (dev→mock, local→ollama) \| `mock` \| `ollama` \| `none` |
| `ZOI_OLLAMA_URL` | `http://127.0.0.1:11434` | Bisa diarahkan ke mesin lain di LAN |
| `ZOI_OLLAMA_MODEL` | *(kosong)* | Wajib diisi di mode local; tidak ada pilihan otomatis yang mengunduh model |
| `ZOI_MOCK_LATENCY_MS` | `300` | Simulasi jeda agar UI loading/streaming teruji |
| `ZOI_AVATAR_MODE` | `auto` | `auto` \| `2d` \| `3d` (3D aktif di Phase 2) |
| `ZOI_CLIPPER_DIR` | *(kosong)* | Folder CLIPPER di mesin ini (read-only bagi ZOI) |
| `ZOI_CLIPPER_PYTHON` | *(kosong)* | Interpreter venv milik CLIPPER (dipakai Phase 7) |
| `ZOI_BLUEPRINT_FILE` | *(kosong)* | Path `Blueprint_Studio.html` |
| `ZOI_EXTRA_ALLOWED_HOSTS` | *(kosong)* | Tambahan allowlist Cost Guard (mis. IP mesin Ollama di LAN) |

Dicadangkan untuk fase berikutnya (belum dibaca di Phase 1): `ZOI_YOUTUBE_*`, `ZOI_STT`, `ZOI_TTS`.
Validasi saat start: nilai tidak dikenal → aplikasi berhenti dengan pesan jelas, tidak menebak.

---

## D. Mock AI Provider — aturan agar tidak menjadi "data palsu"

| Aturan | Implementasi |
|---|---|
| Selalu terlihat sebagai mock | Setiap respons membawa `provider: "mock"`; UI menampilkan lencana **MOCK** di setiap balasan + banner mode |
| Tidak pernah tercampur dengan data asli | Setiap baris yang dihasilkan mock disimpan dengan kolom `is_mock = true`; ekspor data punya opsi `--exclude-mock` (default saat migrasi ke local server) |
| Tidak mengarang statistik | Mock **hanya** menghasilkan teks percakapan & simulasi pemanggilan tool. Mock tidak pernah menghasilkan angka subscriber, views, revenue, atau metrik apa pun |
| Deterministik | Skrip respons berbasis aturan (file JSON di `providers/mock_scripts/`), sehingga tes stabil |
| Menguji jalur yang sama dengan AI sungguhan | Mock mengimplementasikan antarmuka `LLMProvider` yang sama dengan `OllamaProvider`: streaming, tool call, error, timeout. **Contract test** yang sama dijalankan untuk kedua provider |
| Tidak bisa lolos ke mode local | Penjaga saat start + tes otomatis |

---

## E. Struktur folder

```
zoi-command-center/
├─ README.md                      # cara menjalankan di kedua mode, status fitur jujur
├─ LICENSE                        # MIT (diputuskan 14 Nov 2026)
├─ THIRD_PARTY_NOTICES.md
├─ .gitignore                     # data*/, .env, .venv/, node_modules/, dist/
├─ .env.development.example
├─ .env.local.example
├─ docs/
│  ├─ audit/                      # 12 dokumen Phase 0 + rencana ini
│  ├─ adr/                        # 0001 repo terpisah · 0002 dua mode · 0003 mock provider · 0004 data portabel
│  └─ MIGRATION_TO_LOCAL_SERVER.md
│
├─ backend/                                  ── BAGIAN: BACKEND
│  ├─ pyproject.toml · requirements.txt · requirements-dev.txt · alembic.ini
│  ├─ alembic/versions/0001_foundation.py
│  └─ app/
│     ├─ main.py                  # app factory; di mode local juga menyajikan frontend/dist
│     ├─ cli.py                   # zoi-cli: doctor · db upgrade · data export · data import · backup
│     ├─ config/
│     │  ├─ settings.py           # pydantic-settings, membaca .env
│     │  └─ modes.py              # aturan tabel C.1 + validasi saat start
│     ├─ api/                     # health, system, settings, tasks, chat, adapters, ws
│     ├─ core/                    # events, agent_state (11 status), errors
│     ├─ security/                # cost_guard, redact
│     ├─ tasks/                   # manager (antrian, progress, cancel), builtin (system check)
│     │
│     ├─ db/                                 ── BAGIAN: DATABASE
│     │  ├─ base.py · session.py · models.py
│     │  └─ portability.py        # ekspor/impor ZIP + manifest + checksum
│     │
│     ├─ providers/                          ── BAGIAN: AI PROVIDER
│     │  ├─ base.py               # Protocol LLMProvider
│     │  ├─ registry.py           # pilih provider dari mode + env
│     │  ├─ mock.py               # MockProvider
│     │  ├─ mock_scripts/         # skenario respons (JSON)
│     │  └─ ollama.py             # OllamaProvider: health + list_models + chat (dites dengan server tiruan HTTP, tidak memanggil Ollama sungguhan)
│     │
│     └─ integrations/                       ── BAGIAN: INTEGRASI APLIKASI
│        ├─ base.py               # Protocol ExternalAppAdapter: detect(), status()
│        ├─ clipper/adapter.py    # Phase 1: deteksi read-only saja
│        └─ blueprint/adapter.py  # Phase 1: deteksi read-only saja
│
├─ frontend/                                 ── BAGIAN: FRONTEND (npm workspaces)
│  ├─ package.json                # workspaces: apps/*, packages/*
│  ├─ apps/web/                   # command center: layout 5 zona, 16 menu, chat, tasks, settings
│  └─ packages/
│     ├─ avatar/                             ── BAGIAN: AVATAR
│     │  └─ src/{AvatarController.ts, Avatar2D.tsx}   # antarmuka + renderer 2D; 3D masuk Phase 2 tanpa mengubah apps/web
│     └─ api-client/              # klien REST/WS bertipe
│
├─ deploy/
│  └─ windows/                   # target local server = Windows (diputuskan 14 Nov 2026)
│     ├─ install.ps1              # cek disk & Python 3.12, buat venv, pasang requirements — dijalankan pengguna
│     ├─ start.ps1 · stop.ps1     # jalankan/hentikan ZOI di http://127.0.0.1 (port 80)
│     ├─ autostart.ps1            # opsional: daftarkan ke Task Scheduler bawaan Windows (saat login), tanpa layanan pihak ketiga
│     └─ README.md
└─ scripts/
   ├─ dev.sh                      # jalankan backend + Vite di workspace pengembangan
   └─ build_frontend.sh           # menghasilkan frontend/apps/web/dist untuk mode local
```

**Batas antarbagian dijaga oleh tes & aturan lint:**
- `apps/web` hanya boleh memakai avatar lewat `AvatarController` (tidak boleh impor internal).
- Kode di `api/` tidak boleh mengimpor `mock.py` atau `ollama.py` langsung — hanya lewat `registry`.
- `integrations/` tidak boleh mengimpor apa pun dari folder CLIPPER/Blueprint.

---

## F. Database & portabilitas

| Aturan | Alasan |
|---|---|
| Satu file SQLite: `ZOI_DATA_DIR/zoi.db` (mode WAL) | Mudah dipindah |
| Semua path file di database **relatif terhadap `ZOI_DATA_DIR`** | Tetap valid setelah dipindah ke mesin lain |
| Path khusus mesin (CLIPPER, Blueprint, Ollama URL) **hanya di `.env`** | Database tidak terikat satu komputer |
| Waktu disimpan dalam UTC (ISO 8601) | Konsisten lintas mesin |
| Versi skema dicatat Alembic; migrasi otomatis saat start **setelah backup** | Aman saat upgrade |
| `zoi-cli data export` → `zoi-backup-<waktu>.zip` berisi `zoi.db` (setelah *checkpoint* WAL), folder media, `manifest.json` (versi aplikasi, revisi skema, jumlah baris per tabel, SHA-256 setiap file) | Pemindahan satu file, dapat diverifikasi |
| `zoi-cli data import` → validasi checksum & versi → backup data tujuan → pulihkan → migrasi | Tidak menimpa data tanpa backup |

**Tabel Phase 1** (migrasi `0001_foundation`): `app_meta`, `tasks`, `task_events`, `system_checks`, `network_audit`, `conversations`, `messages` (dengan kolom `provider` dan `is_mock`). Preferensi pengguna yang portabel (bahasa UI, mode avatar pilihan) disimpan di `app_meta`; path mesin tidak.

---

## G. Daftar pekerjaan Phase 1 (urutan pengerjaan)

| ID | Pekerjaan | Hasil yang bisa diperiksa |
|---|---|---|
| W-01 | Kerangka repo, lisensi, notices, `.gitignore`, ADR | Repo bersih, dokumen audit ikut tersimpan |
| W-02 | Sistem konfigurasi + validasi mode | Start gagal dengan pesan jelas untuk konfigurasi salah; `local` + `mock` ditolak |
| W-03 | Database + migrasi 0001 + backup sebelum migrasi | Tabel terbentuk; file backup tercipta |
| W-04 | Portabilitas: `data export` / `data import` / `--exclude-mock` | Uji bolak-balik: ekspor → impor ke folder baru → jumlah baris & checksum identik |
| W-05 | API dasar: health, system status (deteksi nyata), settings | Respons berisi `source` & `checked_at` |
| W-06 | Task Manager + WebSocket + 1 task nyata "Pemeriksaan sistem" | Progress tampil langsung, bisa dibatalkan |
| W-07 | Antarmuka `LLMProvider` + `registry` + **MockProvider** | Streaming & simulasi tool call, semua berlabel mock |
| W-08 | **OllamaProvider** (kode saja) | Lulus contract test terhadap server HTTP tiruan; **tidak** memanggil/mengunduh Ollama sungguhan |
| W-09 | Endpoint chat minimal (`POST /api/chat` + stream WS) | Pesan tersimpan dengan `provider` & `is_mock` |
| W-10 | Cost Guard + tes "tanpa SDK berbayar" | Host AI berbayar diblokir & tercatat |
| W-11 | Adapter CLIPPER & Blueprint (deteksi read-only) | Tes hash membuktikan tidak ada file yang berubah |
| W-12 | Frontend: layout 5 zona, 16 menu, chat dasar, Task Manager, Settings, banner mode | 13 menu = "Belum tersedia — Phase N", tanpa angka |
| W-13 | Paket `avatar`: `AvatarController` + Avatar 2D yang mengikuti 11 status nyata | Status berubah sesuai event backend |
| W-14 | Mode local: backend menyajikan `dist` di satu port; skrip `deploy/windows` (install/start/stop/autostart) | `http://127.0.0.1` (port 80) membuka aplikasi utuh tanpa Vite; di workspace dites juga di port alternatif |
| W-15 | `MIGRATION_TO_LOCAL_SERVER.md` + `zoi-cli doctor` (cek Python, disk, port, Ollama, path) | Panduan migrasi langkah demi langkah |
| W-16 | Seluruh tes + laporan | Semua hijau; laporan dilampirkan |

---

## H. Dependensi (diverifikasi dari PyPI & npm, 14 Nov 2026)

**Backend (runtime):** fastapi 0.162.6 (MIT) · uvicorn 0.54.0 (BSD-3) · pydantic 2.14.3 (MIT) · pydantic-settings 2.16.3 (MIT) · sqlalchemy 2.1.8 (MIT) · alembic 1.20.1 (MIT) · httpx 0.28.1 (BSD-3) · psutil 7.2.2 (BSD-3) · structlog 26.1.0 (MIT/Apache-2.0).
**Backend (dev):** pytest 9.2.0 (MIT) · pytest-asyncio 1.5.0 (Apache-2.0) · ruff 0.17.5 (MIT) · pip-audit 2.10.1 (Apache-2.0).
**Frontend (runtime):** react & react-dom 19.3.1 · react-router-dom 7.18.5 · zustand 5.1.0 (semua MIT).
**Frontend (dev):** vite 8.3.8 · @vitejs/plugin-react 6.3.0 · typescript **6.0.3** (bukan 7.x — typescript-eslint belum mendukung) · @types/react(-dom) 19.3.0 · eslint 10.14.0 · typescript-eslint 8.72.2 · vitest 5.1.0 · @testing-library/react 16.3.3 · @testing-library/jest-dom 7.0.1 · jsdom 31.0.1 (MIT) · @playwright/test 1.65.0 (Apache-2.0).

**Tidak ada dependensi baru** untuk Mock Provider, CLI (memakai `argparse` bawaan), dan portabilitas (`zipfile`, `hashlib`, `sqlite3` bawaan).
**Dihapus dari rencana rev. 1:** `keyring` (ditunda ke Phase 6).
**Dilarang & dijaga tes:** openai, anthropic, google-genai, elevenlabs, deepgram, azure-*.

**Lingkungan:**
- Pengembangan (workspace ini): Python 3.12, Node 24 LTS — instalasi paket dilakukan **di workspace**, bukan di laptop; ukuran ±350 MB, bukan proses berat.
- Local server (nanti, **Windows 10/11**): Python 3.12 saja (installer resmi python.org) + frontend yang sudah di-build. Node **tidak** diperlukan di sana.

---

## I. Rencana pengujian

| Kelompok | Tes kunci |
|---|---|
| Konfigurasi | Matriks mode × provider: `development+auto→mock`, `local+auto→ollama`, `local+mock→ditolak`, nilai tidak dikenal → ditolak |
| Provider | Contract test yang sama untuk Mock & Ollama (server HTTP tiruan): streaming, tool call, timeout, error, model `:cloud` ditolak |
| Label mock | Setiap pesan dari mock: `is_mock=true`, `provider="mock"`; mock tidak pernah mengembalikan angka metrik |
| Fallback | Mode local + Ollama mati → status "tidak tersedia", **bukan** mock |
| Database | Migrasi naik/turun; backup tercipta sebelum migrasi |
| Portabilitas | Ekspor → impor ke `ZOI_DATA_DIR` baru → jumlah baris & SHA-256 identik; `--exclude-mock` benar-benar membuang baris mock; impor menolak arsip rusak |
| Path portabel | Tidak ada path absolut di database (dipindai otomatis) |
| Integrasi | Hash seluruh file CLIPPER/Blueprint identik sebelum & sesudah deteksi; tidak ada import modul CLIPPER |
| Keamanan | Bind 127.0.0.1; CORS sesuai mode; log tanpa rahasia; Cost Guard memblokir host AI berbayar |
| Batas antarbagian | Tes impor: `api/` tidak mengimpor provider konkret; `apps/web` hanya memakai API publik paket avatar |
| Frontend | Banner mode tampil di development & tidak di local; lencana MOCK di balasan; 13 menu tanpa angka |
| E2E (Playwright, di workspace) | Desktop 1440 px & mobile 375 px: tanpa geser horizontal, chat mock, task berjalan & dibatalkan |
| Mode local | Build frontend → backend menyajikan di satu port → E2E lulus tanpa Vite |
| Supply chain | pip-audit, npm audit, pemeriksaan lisensi otomatis |

---

## J. Dampak perubahan

| Objek | Dampak |
|---|---|
| ZOI AI CLIPPER | **Tidak ada** — 0 file diubah, tidak di-import |
| Blueprint Studio | **Tidak ada** — tidak diubah, tidak dipublikasikan |
| Laptop saat ini | **Tidak ada** selama Phase 1 — 0 MB instalasi, 0 proses |
| Workspace pengembangan | Instalasi paket ±350 MB (dihapus otomatis saat sesi berakhir) |
| GitHub | Repo private baru (kamu yang membuat) |
| Project claude.ai | `audit/PHASE1_PLAN.md` diganti revisi ini; nanti ditambah `MIGRATION_TO_LOCAL_SERVER.md` |
| Rencana fase selanjutnya | Phase 3 → "Ollama Provider di local server" (memakai kode W-08). Ditambah **Phase 11: Migrasi ke local server** (instal Python, salin repo + `dist`, isi `.env.local`, impor data `--exclude-mock`, jalankan `doctor`, buka `http://127.0.0.1:<port>`) |
| Biaya | Rp0. Tidak ada layanan berbayar |

---

## K. Risiko & mitigasi

| ID | Risiko | Mitigasi |
|---|---|---|
| R-1 | Mock terlalu "pintar" sehingga perilaku Ollama nanti berbeda | Contract test bersama + skenario mock meniru keterbatasan nyata (JSON rusak, timeout, tool call salah format) |
| R-2 | Dikembangkan di Linux, dijalankan di Windows | `pathlib` di semua path (aman untuk spasi & huruf besar/kecil), tanpa perintah shell khusus OS, output konsol UTF-8, file dibuka dengan encoding eksplisit; ekspor database memakai *SQLite backup API* (aman meski file sedang dibuka — Windows mengunci file terbuka); `.gitattributes` menjaga `.ps1` tetap CRLF. Tes jalur Windows disimulasikan di workspace; uji akhir di Windows nyata saat migrasi |
| R-3 | Data mock ikut terbawa ke local server | Default ekspor migrasi `--exclude-mock` + mode local menandai sisa data mock dengan peringatan |
| R-4 | Port 80 (default mode local) bisa sudah dipakai: di Windows oleh IIS / layanan HTTP.sys / Skype lama / XAMPP; di Linux butuh hak khusus untuk port < 1024 | `zoi-cli doctor` memeriksa port 80 sebelum start dan menyebut proses yang memakainya. Jika terpakai, aplikasi **tidak** mematikan layanan lain; ia berhenti dengan pesan jelas dan saran `ZOI_PORT=8000`. Di Windows, port 80 tidak butuh hak Administrator, tetapi sering dipakai IIS/HTTP.sys; `doctor` memeriksanya dengan `Get-NetTCPConnection` |
| R-5 | Spesifikasi local server belum diketahui | Konfigurasi `ZOI_AVATAR_MODE` & `ZOI_AI_PROVIDER` menyesuaikan tanpa ubah kode |

---

## L. Keputusan yang saya butuhkan

1. **Setujui** rencana revisi 2 ini (atau sebutkan bagian yang diubah).
2. **Repo GitHub:** buat repo kosong private (saran: `zoi-command-center`), lalu beri tahu namanya.
3. ~~Lisensi repo~~ — **DIPUTUSKAN: MIT** (14 Nov 2026).
4. ~~Port default local server~~ — **DIPUTUSKAN: 80** untuk mode local (14 Nov 2026); development tetap 8000.
5. ~~Chat minimal di Phase 1 (W-09)~~ — **DIPUTUSKAN: ikut Phase 1** (14 Nov 2026).
6. ~~OS local server~~ — **DIPUTUSKAN: Windows** (14 Nov 2026). Skrip Linux tidak dibuat di Phase 1.
