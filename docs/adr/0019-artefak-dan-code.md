# ADR 0019 — Artefak dan ZOI Code

Status: diterima (1.2.9)

## Konteks
Pengguna ingin fitur seperti Claude: (1) **artefak**, yaitu halaman HTML satu file yang bisa dibuka lewat tautan, dan
(2) **Claude Code**, yaitu agen yang membaca, menulis, dan menguji kode. Aturan proyek tetap berlaku: AI gratis
(NVIDIA NIM / OpenRouter `:free` / Ollama), tanpa publikasi, tanpa kredensial di frontend, dan berhenti bila berisiko.

## Keputusan
**Artefak** (`app/artifacts.py`, `/artefak`, `/artefak/<id>`)
- AI ZOI menulis/merevisi HTML sebagai tugas latar (`artifact_generate`). Pengguna juga bisa mengunggah HTML sendiri.
  Maksimal 10 versi disimpan, ada tombol kembali ke versi sebelumnya.
- Disajikan di `/artefak-raw/<id>/` dengan `Content-Security-Policy: sandbox allow-scripts …` **tanpa
  allow-same-origin**, sehingga origin-nya buram. Kode artefak tidak bisa memanggil `/api`, membaca cookie, atau
  menyentuh data ZOI. `connect-src` hanya `data:`/`blob:`/CDN umum.
- `window.claude.use("sample")` (`.json`/`.text`) dan `"downloads"` disisipkan sebagai shim. Panggilan dijembatani
  lewat `postMessage` ke halaman penampil ZOI, yang memeriksa `event.source` (harus iframe miliknya), membatasi
  20 panggilan AI per menit, lalu memanggil `/api/artifacts/sample`. Tanpa penampil, `sample` bernilai `null`, jadi
  artefak memakai jalur cadangannya sendiri.

**ZOI Code** (`app/code_agent.py`, `/code`)
- Loop berulang: AI membalas satu JSON `{alat,args}` atau `{selesai}`. Alatnya: `daftar`, `baca`, `tulis`, `ganti`,
  `cari`, `jalankan`, `hapus`. Maksimal 30 langkah per perintah, dan riwayat lama diringkas agar muat di konteks
  16k token.
- Hanya di folder `<data>/kode/<proyek>/`. Jalur absolut, `..`, dan symlink keluar ditolak, dan `.zoi/` dilindungi.
  Setiap tulis/hapus disalin dulu ke `.zoi/cadangan/`.
- `jalankan` dan `hapus` **selalu menunggu izin** (sekali, atau "semua di sesi ini"). Perintah berjalan di folder
  proyek dengan batas 180 detik, tanpa stdin, dan tanpa variabel `ZOI_*`/`*KEY*`/`*TOKEN*`/`*SECRET*`. Perintah
  perusak sistem (format, shutdown, diskpart, `rm -rf /`, …) diblokir walau diizinkan.
- Artefak dan Code **dimatikan di mode online** (server publik).

## Konsekuensi
- Model gratis lebih lemah dari Claude. Artefak sederhana sampai menengah dan tugas kode kecil berjalan baik,
  sedangkan aplikasi besar tetap paling baik dibuat di Claude lalu diunggah sebagai artefak.
- Sesi Code disimpan di memori: hilang bila ZOI dimulai ulang, tetapi file proyeknya tetap ada.
