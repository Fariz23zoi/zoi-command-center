# ARCHITECTURE.md — Arsitektur Final yang Diusulkan

Status: USULAN, menunggu persetujuan. Belum ada kode.

## 1. Gambaran besar

```
┌──────────────────────────── BROWSER (laptop / HP di LAN) ────────────────────────────┐
│  ZOI 3D AI COMMAND CENTER  — React + TypeScript + Vite                                │
│  ┌ Nav kiri ┐ ┌──── Avatar ZOI (R3F + talking-avatar) ────┐ ┌ Panel kanan ──────────┐ │
│  │16 menu   │ │ state: IDLE/LISTENING/THINKING/SPEAKING…  │ │ insight, task, kuota  │ │
│  └──────────┘ └───────────────────────────────────────────┘ └───────────────────────┘ │
│  Chat + tombol mic + stop bicara (bawah)       Channel selector + status sistem (atas) │
└───────────────▲──────────── REST (JSON) + WebSocket /ws (status, stream token, audio) ─┘
                │
┌───────────────┴──────────── BACKEND ZOI — Python 3.11/3.12 + FastAPI (127.0.0.1:8000) ──┐
│ API layer ── Pydantic validation ── Permission Manager ── Cost Guard (whitelist host)  │
│                                                                                        │
│ AGENT CORE                                                                             │
│  Planner → Tool Registry → Executor → Result Evaluator                                 │
│  Context Manager · Memory Manager · Task Manager (antrian + cancel + progress)         │
│  LLM Provider abstraction:  OllamaProvider (default) | (slot kosong untuk provider lain│
│                              — tidak ada provider berbayar terpasang)                  │
│                                                                                        │
│ SERVICES                                                                               │
│  Voice:   STT faster-whisper  ·  TTS Piper (subprocess)                                │
│  YouTube: DataAPI client · AnalyticsAPI (OAuth) · QuotaTracker · SnapshotCollector     │
│  Intel:   ChannelAnalytics · Competitor · ViralHunter · TrendDetector · ContentGap     │
│           IdeaGen · ScriptStoryboard · UploadTime · Retention · Monetization           │
│  Adapters: ClipperAdapter (import shorts_generator)  ·  BlueprintAdapter (paket JSON)  │
│  Scheduler: APScheduler (job tersimpan di SQLite)                                      │
│                                                                                        │
│ STORAGE: SQLite (SQLAlchemy 2 + Alembic) · folder data/ (media, paket, backup, log)    │
└───────┬──────────────────────┬──────────────────────────┬──────────────────────────────┘
        │                      │                          │
  Ollama :11434          ZOI AI CLIPPER             BLUEPRINT STUDIO
  (qwen3:8b default)     (repo terpisah, tidak       (HTML; disajikan statis oleh ZOI)
                          diubah — dipanggil          + HyperFrames CLI untuk render MP4
                          sebagai library)
        │
  Internet hanya untuk: googleapis.com (YouTube API, OAuth), youtube.com (yt-dlp, atas perintah),
  unduh dependency/model (dengan persetujuan).
```

## 2. Keputusan teknologi (dan alasannya)

| Area | Pilihan | Alasan / alternatif yang ditolak |
|---|---|---|
| Frontend | **Vite + React + TypeScript** | Aplikasi lokal tanpa SEO/SSR → Next.js tidak perlu dan lebih berat |
| 3D | three.js + React Three Fiber + drei (seperlunya) | Standar; talking-avatar kompatibel |
| Avatar & lip-sync | **talking-avatar** (MIT) + avatar Rocketbox, di-self-host | Gratis, lip-sync dari audio lokal; riverbornai ditolak (4 API berbayar) |
| State UI | Zustand | Ringan; Redux tidak perlu |
| Backend | **FastAPI** | Sesuai stack; WebSocket bawaan |
| Database | SQLite + SQLAlchemy 2 + Alembic | Lokal, satu file, mudah backup |
| Background job | `asyncio` + ThreadPool untuk kerja berat, status di SQLite | Celery/Redis ditolak: dependency berlebihan untuk satu pengguna |
| Penjadwal | APScheduler | Lokal, bisa dihentikan, tercatat |
| LLM | Ollama (HTTP API) | Ganti model tanpa ubah kode |
| STT | faster-whisper (backend) → fallback Web Speech (dengan izin) | |
| TTS | Piper (proses terpisah, GPL dipisah) → fallback speechSynthesis | |
| Grafik | **Recharts/ECharts di frontend**; Pandas di backend | Plotly diganti karena bundle berat di HP — Plotly tetap opsi untuk laporan |
| Tes | pytest + httpx, Vitest + Testing Library, Playwright (E2E + cek mobile) | |

## 3. Abstraksi provider AI
```python
class LLMProvider(Protocol):
    name: str
    def health(self) -> ProviderStatus: ...          # koneksi, model aktif, RAM/VRAM, error
    def list_models(self) -> list[ModelInfo]: ...
    async def chat(self, messages, tools=None, stream=True) -> AsyncIterator[Chunk]: ...
```
Registri provider hanya berisi `OllamaProvider`. Jika Ollama mati / model belum ada → status `UNAVAILABLE` + instruksi instalasi; **tidak ada fallback diam-diam ke cloud**.

## 4. Status agent ↔ avatar
Satu sumber kebenaran: event WebSocket `agent.state` dari backend.

| Status backend | Animasi avatar | Sumber nyata |
|---|---|---|
| IDLE | idle + kedip + gerak kepala halus | tidak ada task |
| LISTENING | listening | mic aktif / STT berjalan |
| THINKING / PLANNING | thinking | LLM sedang merencanakan |
| RESEARCHING | researching | tool YouTube API berjalan |
| ANALYZING | analyzing | tool analitik berjalan |
| CREATING | creating | generator naskah/ide/paket |
| EXECUTING | working | CLIPPER/HyperFrames render |
| WAITING_APPROVAL | menunggu (kepala miring, tanda ?) | permission request terbuka |
| SPEAKING | speaking + lip-sync | audio TTS diputar |
| COMPLETED | success | task selesai |
| FAILED | error | task gagal |

Avatar Rocketbox bawaan hanya close-up wajah: ekspresi (ARKit blendshape) + gerak kepala/mata **tersedia**; animasi tubuh **tidak tersedia** sampai ada model ber-rig + klip animasi — akan dilabeli jelas di UI.

## 5. Mode data
`API CONNECTED` · `LOCAL DATA` (cache/snapshot) · `MANUAL IMPORT` (CSV ekspor YouTube Studio) · `DEMO MODE` (data contoh **berlabel DEMO di setiap kartu**, tidak pernah tercampur dengan data asli).

## 6. Skema database (awal)
`users, channels, videos, competitors, analytics_snapshots, video_snapshots, content_ideas, scripts, storyboards, production_packages, tasks, task_events, conversations, messages, memories (scope: long_term|project|conversation), production_history, experiments, monetization_progress, quota_usage, automations, automation_runs, settings`.
Setiap baris metrik punya kolom `source`, `fetched_at`, `method`, `label (FACT|ESTIMATE|HYPOTHESIS)`, `confidence`.

## 7. Struktur repo ZOI (baru, terpisah dari CLIPPER)
```
zoi-command-center/
  backend/  app/{api,agent,providers,services,adapters,db,scheduler,security}  tests/
  frontend/ src/{components,avatar,pages,stores,lib}  public/avatars  public/models
  docs/     (10 dokumen audit ini + panduan)
  scripts/  check_env.ps1, backup_db.py
  THIRD_PARTY_NOTICES.md  COST_CONTROL.md
```
CLIPPER dan Blueprint Studio tetap di lokasinya sendiri; ZOI mereferensikannya lewat path di Settings.
