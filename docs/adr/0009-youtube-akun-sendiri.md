# ADR 0009 — YouTube: OAuth desktop hanya-baca, token di Credential Manager, tanpa metrik turunan

**Status:** diterima (15 Nov 2026). Keputusan pengguna (Phase 6): K-1 status OAuth **In production** (belum
diverifikasi), K-2 fitur kompetitor/viral/tren **dirancang ulang agar patuh** (Phase 6B), K-3 **tanpa scope
pendapatan**, K-4 token di **Windows Credential Manager**. Phase 6A hanya mencakup channel milik pengguna.

**Fakta yang dipakai** (halaman resmi Google/YouTube, dicek 14–15 Nov 2026):
- YouTube Data API: 10.000 unit/hari per project, metode baca 1 unit, reset tengah malam waktu Pasifik.
- Kebijakan Developer: data berizin milik pengguna boleh disimpan >30 hari bila izin dicek ulang tiap 30 hari
  (III.E.4.b); dilarang membuat metrik turunan dari data API (III.E.4.h); data dihapus saat izin dicabut (III.E.4.g).
- Aplikasi desktop: OAuth authorization code + PKCE, redirect loopback `http://127.0.0.1:port`. *Client secret*
  aplikasi desktop tidak dianggap rahasia oleh Google, tetapi tetap tidak boleh masuk repo.
- Status "Testing" membuat refresh token kedaluwarsa 7 hari → dipakai "In production".

**Keputusan.**
- **Scope hanya-baca:** `youtube.readonly` dan `yt-analytics.readonly`. Tidak ada scope unggah, kelola, atau
  pendapatan. Tes memeriksa URL izin tidak memuat scope lain.
- **Alur:** pengguna mengimpor file client OAuth bertipe *Desktop app* lewat UI (bukan `.env`; file bertipe *Web*
  ditolak; alamat endpoint di dalam file diabaikan). ZOI membuka pendengar sekali-pakai di `127.0.0.1` port acak,
  memeriksa `state` (perbandingan waktu-konstan), menukar kode dengan `code_verifier`, mewajibkan refresh token
  dan scope `youtube.readonly`, lalu memastikan akun punya channel. Gagal di langkah mana pun → tidak ada yang
  tersimpan. Batas waktu 5 menit. ZOI tidak pernah melihat password Google.
- **Penyimpanan rahasia:** refresh token di keyring sistem (`keyring` → Windows Credential Manager). Bila keyring
  tidak ada (mis. Linux tanpa desktop), token disimpan di `data/secrets/tokens.json` dan UI menyatakan terus
  terang bahwa file itu **tidak terenkripsi**. Access token hanya di memori. Folder `secrets` (token + file
  client) tidak pernah ikut `data export`, tidak ada di database, log, respons API, atau browser.
- **Cost Guard:** hanya lima host Google yang sudah ada di allowlist eksak; tidak ada host baru.
- **Kuota:** ZOI menghitung sendiri setiap panggilan sebelum dikirim dan berhenti di 90% (9.000 unit; pencarian
  90/hari untuk Phase 6B). Angka kuota diberi label "hitungan ZOI", bukan angka dari YouTube.
- **Data:** tabel `youtube_cache` (respons terakhir channel/video/laporan), `youtube_channel_snapshots` (satu baris
  per hari pengambilan), `youtube_quota` (migrasi 0004). Bila izin tidak terverifikasi >30 hari, data dihapus
  otomatis (akun tetap tersambung); "Ambil data terbaru" memverifikasi ulang. "Putuskan & hapus data" mencabut
  token di Google (best-effort, dilaporkan bila gagal) dan menghapus token + seluruh data seketika.
- **Tanpa metrik turunan:** angka ditampilkan persis seperti dikirim YouTube (hanya pemisah ribuan), masing-masing
  dengan sumber dan waktu ambil. Halaman Monetization menaruh syarat resmi YPP (`ypp.json`, dengan tautan sumber
  dan tanggal cek) **berdampingan** dengan angka channel — tanpa persentase, sisa, atau perkiraan. Menit ditonton
  dari Analytics diberi keterangan bahwa itu bukan "jam tonton publik yang sah". Kabar perubahan syarat Februari
  2027 hanya dari sumber pihak ketiga → ditandai "belum terverifikasi".
- **Agen:** `youtube_channel_saya` dan `youtube_video_saya` bertingkat `external` (selalu minta izin, memakai
  kuota); `youtube_kuota` bertingkat `read`. Tidak ada tool yang menulis ke YouTube.
- **Pengujian:** `ZOI_YOUTUBE_TEST_URL` (hanya `http://` loopback; ditolak selain itu) mengarahkan semua endpoint
  ke `tests/fake_google.py`. Saat aktif, peringatan muncul di log dan setiap halaman menampilkan "ENDPOINT UJI".

**Konsekuensi.**
- Seluruh alur diuji terhadap Google **tiruan**; koneksi pertama ke Google sungguhan terjadi di komputer pengguna
  (checklist di `docs/MIGRATION_TO_LOCAL_SERVER.md`). Bentuk respons tiruan mengikuti dokumentasi resmi, tetapi
  belum dibandingkan dengan respons asli.
- Aplikasi OAuth "In production" yang belum diverifikasi menampilkan layar "Google hasn't verified this app" dan
  dibatasi 100 pengguna — cukup untuk pemakaian pribadi.
- `keyring` di Windows menarik `pywin32-ctypes` (BSD-3-Clause menurut metadata PyPI); paket itu tidak terpasang di
  workspace Linux sehingga belum tercantum di `THIRD_PARTY_NOTICES.md` — jalankan ulang `check_licenses.py`
  setelah instalasi di Windows.
- Data YouTube ikut `data export` (database), tetapi token tidak. Setelah impor di komputer lain, ZOI meminta
  hubungkan ulang.
