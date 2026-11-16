# ADR 0016 — ZOI Universe V2: dua permukaan, satu aplikasi

Status: diterima (16 Nov 2026) · Versi 1.2.0

## Keputusan
- **Satu backend, satu build frontend, dua layout**: ZOI Universe (`/`, `/dashboard`, halaman fitur) dan workspace
  ZOI 3D AI Agent (`/ai`). Tidak ada server/proses kedua (laptop 7 GB RAM).
- Halaman publik (landing, about, products, technology, contact) tanpa three.js; three + React Three Fiber hanya
  dimuat (lazy) saat kantor 3D tampil di `/ai` pada layar lebar.
- Avatar: robot ZOI low-poly di kantor isometrik; zona mengikuti status agen nyata (`ai/zones.ts`). Close-up lama
  (2D / Rocketbox 3D dengan lip-sync) tetap dipakai di HP, sub-halaman `/ai/*`, dan sebagai fallback FPS rendah.
- Dashboard = Dual YouTube Analytics (My Channel / Competitors), lihat `docs/redesign/DUAL_ANALYTICS.md`.
- Provider AI tetap hanya yang gratis. Registry produk di `products.ts`; CLIPPER tetap ditunda, AI Lab "planned".
- Rute lama tetap berlaku (`/analytics`, `/settings`, …); `/` kini landing, Overview lama → `/diagnostics`,
  `/assistant` → workspace AI.

## Konsekuensi
- Layout lama `CommandCenter` (5 zona) dihapus; chat hanya ada di `/ai`.
- Tidak ada migrasi database baru; endpoint baru hanya menambah.
- Pemulihan: branch `checkpoint/pre-redesign` (v1.1.1).
