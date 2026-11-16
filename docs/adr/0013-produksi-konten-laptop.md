# ADR 0013 — Produksi konten di laptop: paket, narasi, salinan Blueprint Studio, HyperFrames opsional

Tanggal: 16 November 2026 · Status: diterima

## Konteks
ZOI kini berjalan online (ADR 0012), tetapi produksi konten tetap di laptop. Keputusan pengguna Phase 7:
CLIPPER ditunda (yt-dlp melanggar ketentuan YouTube), tombol "Muat paket ZOI" di **salinan** Blueprint Studio
(asli tidak diubah, tidak dipublikasikan), HyperFrames hanya opsi tambahan yang dipasang pengguna sendiri.

## Keputusan
1. **Paket `zoi.paket/v1`** (ADR 0012, Bagian B) adalah satu-satunya jembatan online → laptop. Di laptop paket
   disimpan sebagai file di `data/production/<id>/` (paket.json, narasi.wav, narasi.srt, waktu.json, video.mp4).
   Hanya nama file yang terdaftar yang bisa diunduh; id dibatasi 12 heksadesimal.
2. **Narasi** memakai `VoiceService.speak` (Piper, syarat lisensi Phase 4 tetap berlaku) per beat, digabung
   dengan jeda 0,3 detik. SRT dibuat per beat dari durasi audio sungguhan, bukan perkiraan.
3. **Salinan Blueprint**: penanda struktur (judul, id elemen, `render()`, `setMode()`, `state={beats:`) wajib
   ada; bila tidak, salinan ditolak. Tambahan hanya satu blok `<script>` sebelum `</body>` yang memanggil
   fungsi milik Blueprint sendiri. Kode Blueprint tidak masuk repo. Halaman `/blueprint-studio/` memakai CSP
   sendiri: `'unsafe-inline'` hanya untuk skrip asli Blueprint, font Google yang memang dipakai file asli,
   `connect-src 'self'`.
4. **HyperFrames** (Apache-2.0, diuji v0.9.55): dijalankan `node <ZOI_HYPERFRAMES_DIR>/node_modules/hyperframes/
   bin/hyperframes.mjs render` — tanpa `npx` unduhan. `HYPERFRAMES_BROWSER_PATH` selalu menunjuk Chrome/Edge
   terpasang (HyperFrames bisa mengunduh Chrome sendiri — dicegah), `HYPERFRAMES_NO_TELEMETRY=1`, `DO_NOT_TRACK=1`.
   Tidak memakai render cloud/billing HyperFrames. Templat memakai animasi CSS saja; GSAP tidak dipakai karena
   lisensinya bukan open source. Render = tugas yang bisa dibatalkan (proses dimatikan), batas 60 menit.
5. Mode online: semua endpoint produksi menjawab 409 "hanya di laptop"; halaman menjelaskan alurnya.

## Konsekuensi
- Kualitas video HyperFrames = kartu teks sederhana; animasi berkualitas tetap lewat Blueprint + Claude.
- Perubahan besar pada Blueprint Studio bisa membuat salinan ditolak — disengaja.
- Laptop E1-6010: render diperkirakan sangat lambat (1 worker, ±256 MB per proses Chrome); belum diukur di sana.
