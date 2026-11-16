# ADR 0001 — Repo ZOI terpisah; aplikasi lama tidak diubah

**Status:** diterima (14 Nov 2026)

**Konteks.** ZOI AI CLIPPER dan Blueprint Studio sudah berfungsi dan tidak boleh rusak.

**Keputusan.** ZOI dibangun di repo baru `zoi-command-center`. Aplikasi lama hanya diakses lewat adapter di
`backend/app/integrations/`. Di Phase 1 adapter hanya **mendeteksi** (cek keberadaan file, membaca maksimal
8 KB HTML Blueprint) — tidak meng-import, menjalankan, atau menulis. Path aplikasi lama hanya ada di `.env`.

**Akibat.** Tes `test_adapters_readonly.py` membandingkan SHA-256 + ukuran + waktu modifikasi semua file
aplikasi lama sebelum dan sesudah deteksi. Perubahan apa pun di aplikasi lama butuh persetujuan terpisah.
