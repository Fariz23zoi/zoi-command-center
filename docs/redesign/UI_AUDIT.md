# UI_AUDIT — ZOI Universe V2 (Phase 1)

Tanggal: 16 Nov 2026 · Basis: `main` 4b7b2f1 (v1.1.1) · Titik pemulihan: branch `checkpoint/pre-redesign`

## Stack saat ini
| Lapisan | Teknologi |
|---|---|
| Frontend | React 19.3, Vite 8, TypeScript, react-router-dom 7.18, zustand 5.1 — monorepo `frontend/apps/web` + `packages/{api-client,avatar}` |
| Styling | Satu file `styles/app.css` (198 baris), CSS variables, tanpa framework UI |
| Avatar | `@zoi/avatar`: 2D (CSS, lingkaran + mata) dan 3D (`@interviewflowai/talking-avatar` 0.3.0 + three 0.187, model Rocketbox, lazy chunk), benchmark FPS → fallback 2D |
| Backend | FastAPI, SQLAlchemy 2 + Alembic (8 migrasi), SQLite lokal / Postgres online |
| Tes | 313 tes backend (pytest), vitest, 9 spesifikasi Playwright E2E |

## Halaman & rute (semua berfungsi, harus dipertahankan)
Layout tunggal `CommandCenter` = TopBar + SideNav (17 menu) + CenterStage (avatar) + BottomBar (chat/input).

| Rute | Halaman | Data |
|---|---|---|
| `/` | Overview | Status sistem, provider AI, aplikasi terintegrasi |
| `/assistant` | AI Assistant | Chat + agen (rencana tool dengan izin) via WebSocket |
| `/analytics`, `/performance`, `/monetization` | YouTube milik sendiri | OAuth resmi, read-only |
| `/competitors`, `/viral`, `/trends` | Data publik YouTube | API resmi |
| `/ideas`, `/script` | Draf konten AI | AI lokal/cloud |
| `/production`, `/blueprint` | Paket produksi, Piper, Blueprint (salinan), HyperFrames | Laptop |
| `/clipper` | ZOI AI CLIPPER | **Ditunda** (yt-dlp vs ketentuan YouTube); hanya deteksi read-only |
| `/automation`, `/tasks`, `/memory` | Jadwal, tugas latar, memori | DB |
| `/settings` + `/settings/{ai,voice,youtube,ai-cloud}` | Konfigurasi | `.env` + Credential Manager |
| AuthGate | Login (hanya mode online) | |

## Masalah UI (alasan redesign)
1. Semua fungsi (chat, avatar, 17 menu) dalam satu layout → padat; tidak ada pemisahan "platform" vs "aplikasi AI".
2. Overview menampilkan detail teknis (CPU/RAM/Ollama/Whisper) yang sebaiknya di Diagnostics.
3. Avatar 2D generik; avatar 3D = wajah manusia realistis (bukan identitas ZOI), tanpa ekspresi/gerak kepala.
4. Tidak ada landing page / halaman produk.
5. Mobile: layout dasar responsif, belum ada drawer menu & chat layar penuh.
6. Gaya visual minim (satu CSS), tanpa design tokens yang terstruktur.

## Yang TIDAK boleh rusak
API `/api/*` & WebSocket, migrasi DB, mode development/local/online, penyimpanan key (Credential Manager / terenkripsi), proteksi Tailscale (`remote_denied`), CSP, voice (Whisper/Piper/browser), agen + izin tool, semua tes yang ada.
