# ARCHITECTURE — ZOI Universe V2

Prinsip: **satu backend, satu build frontend, dua "permukaan" (surface)**. Tidak ada framework baru, tidak ada server kedua — penting untuk laptop 7 GB / 2 thread.

```
Browser ── https://<laptop>.ts.net  atau  http://127.0.0.1
   │
   ├─ /                ZOI UNIVERSE (platform)   ← layout UniverseShell
   │   ├─ /            Landing
   │   ├─ /about /products /products/:id /projects /technology /contact
   │   ├─ /dashboard   User Dashboard (data nyata)
   │   ├─ /account     Account Settings
   │   └─ /app/*       semua halaman lama (YouTube, produksi, otomasi, settings) — rute lama di-redirect
   │
   └─ /ai/*            ZOI 3D AI AGENT (workspace)  ← layout AgentShell, lazy chunk
       ├─ /ai          chat + avatar + input + suara
       ├─ /ai/c/:id    percakapan tersimpan
       └─ /ai/{models,agents,tools,memory,settings}
   │
FastAPI (tetap) ── /api/* + /ws ── SQLite/Postgres ── Ollama / NVIDIA NIM / OpenRouter
```

## Keputusan
| Area | Keputusan |
|---|---|
| Routing | `react-router` yang ada; dua layout route; rute lama tetap jalan lewat redirect (bookmark tidak rusak). |
| Code splitting | `React.lazy` per surface; landing tidak memuat three.js; workspace AI memuat avatar hanya bila dibuka. |
| Design system | `packages/ui` baru: tokens CSS (warna dari spesifikasi), komponen dasar (Button, Card, Sidebar, Drawer, Badge, StatusDot). Tanpa library UI berat. |
| Auth | Tidak diubah. Mode local = satu pengguna (identitas Tailscale bila via HP); mode online = login yang ada. Satu sesi berlaku untuk kedua surface karena satu origin. |
| Produk | Registry produk statis di frontend (`products.ts`) + status nyata dari `/api/system` (integrasi). CLIPPER & Blueprint lewat adapter yang ada, repo asli tidak disentuh. |
| Provider AI | Arsitektur adapter sudah ada (`providers/registry.py`, `ai/cloud.py`). Provider baru ditambah sebagai adapter OpenAI-compatible — **hanya yang gratis** (lihat roadmap, butuh persetujuan). |
| Avatar 3D | Avatar ZOI orisinal low-poly prosedural (three.js; R3F + Drei bila disetujui, MIT). Status: idle/thinking/listening/speaking + ekspresi dasar; titik kait lip-sync dari amplitudo audio. Batas FPS 30, DPR ≤1.5, pause saat tab tersembunyi, fallback 2D (dipertahankan). |
| Data | Tidak ada tabel dihapus. Tambahan (riwayat percakapan multi-chat, usage) = migrasi baru `0009_*` yang hanya menambah. |
