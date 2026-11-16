# ADR 0005 — Avatar 3D dengan talking-avatar (Opsi A)

**Status:** diterima (14 Nov 2026) — pilihan pengguna: "Opsi A: talking-avatar".

**Keputusan.**
- Avatar 3D memakai `@interviewflowai/talking-avatar@0.3.0` (MIT) dengan `three@0.187.0` (MIT), versi dikunci persis.
  Wajah Microsoft Rocketbox (MIT) close-up, lip-sync dari audio (model 1 MB yang berjalan di browser), kedip, alis.
- Semua aset (`female.glb`, `male.glb`, `viseme-model.bin`, dua file lisensi) disalin dari `node_modules` ke
  `avatar-assets/` saat build (`scripts/copy-avatar-assets.mjs`) dan disajikan server ZOI sendiri. **Tidak ada CDN.**
  E2E memastikan tidak ada satu pun permintaan ke host lain.
- `Avatar3D` dimuat lazy (chunk terpisah ±276 KB gzip) — mode 2D tidak mengunduh three.js sama sekali.
- Pemilihan renderer ada di `@zoi/avatar`, bukan di aplikasi:
  1. `ZOI_AVATAR_MODE=2d` di server memaksa 2D (profil lite / laptop lemah). Pilihan di Settings dikunci.
  2. Preferensi pengguna (`auto` / `2d` / `3d`, ikut tersimpan dan terekspor).
  3. Browser tanpa WebGL 2 atau AudioWorklet → 2D dengan alasan tertulis.
  4. Mode `auto`: uji FPS 5 detik setelah avatar tampil; di bawah 20 fps → 2D, hasil disimpan per browser,
     bisa diuji ulang di Settings. Gagal memuat aset → 2D dengan alasan.
- Status ZOI dipetakan: status kerja (THINKING, PLANNING, RESEARCHING, ANALYZING, CREATING, EXECUTING) → `thinking`,
  lainnya → `listening`. Warna cincin + label menunjukkan status persisnya (sama dengan avatar 2D).
- `AvatarController.speak(audio)` disiapkan untuk suara ZOI di Phase 4. Saat ini hanya dipakai tombol
  "Uji lip-sync" di Settings dengan file audio dari perangkat pengguna; file tidak dikirim ke server.

**Pengecualian CSP (mode local).** `script-src 'self' blob: 'wasm-unsafe-eval'`, `worker-src 'self' blob:`,
`media-src 'self' blob:`, `connect-src` menambah `blob:`. Alasan: AudioWorklet paket dibuat dari blob URL, dan
decoder meshopt three.js (aset GLB terkompresi) memakai WebAssembly. Tetap tanpa `'unsafe-eval'` dan tanpa host luar.

**Keterbatasan yang diterima (dinyatakan di Settings).** Tidak ada gerak kepala, arah pandang, atau ekspresi
senyum/cemberut; hanya wajah close-up. Render terus-menerus ±60 fps (antialias, pixel ratio ≤ 2) — itulah sebabnya
ada uji FPS dan pemaksaan 2D. Laptop E1-6010 diperkirakan tetap 2D.

**Alternatif ditolak.** TalkingHead (perlu aset Ready Player Me/rig sendiri, lebih berat), avatar VRM
(lisensi model per-karakter beragam), membuat rig sendiri (waktu).
