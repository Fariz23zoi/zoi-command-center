# SECURITY_AUDIT.md — Phase 0

Cakupan: repo `zoi-ai-clipper` (commit 29d1738), `Blueprint_Studio.html`, dan rencana ZOI. Tidak ada perbaikan dilakukan.

## 1. Pemeriksaan rahasia (FACT)
- Pencarian pola API key (`sk-…`, `sk-ant-…`, `AIza…`, `api_key = "…"`) di seluruh file CLIPPER: **tidak ditemukan**.
- `.env` ada di `.gitignore`; hanya `.env.example` dengan placeholder yang ter-commit. ✅
- Repo CLIPPER **private** di GitHub. ✅
- Catatan: riwayat Git hanya dicek pada snapshot dangkal (depth 1); commit lama belum diperiksa. Rekomendasi: jalankan `gitleaks` pada riwayat penuh di Phase 1 (gratis, open-source).

## 2. ZOI AI CLIPPER

| ID | Temuan | Tingkat | Rekomendasi |
|---|---|---|---|
| S-01 | `app.run(host="0.0.0.0")` tanpa autentikasi | **Tinggi** bila di Wi-Fi publik | Default `127.0.0.1`; akses LAN hanya lewat opsi eksplisit + token |
| S-02 | Form `/analyze` menerima input bebas; `download_youtube_local()` menerima **path file lokal** dan URL apa pun yang didukung yt-dlp | Sedang | Batasi ke `http(s)` domain YouTube; path lokal hanya dari folder yang diizinkan |
| S-03 | Tidak ada proteksi CSRF pada `/analyze` dan `/select` | Sedang (lokal) | Token CSRF atau API JSON + header khusus |
| S-04 | `/select` menerima `source_path` dari form | Rendah — **sudah divalidasi** dengan `realpath` + harus di dalam `output/` ✅ | Pertahankan; ganti dengan ID job |
| S-05 | `/output/<path>` menyajikan semua isi `output/` (video sumber, transkrip, audio) | Rendah | Sajikan hanya file hasil render |
| S-06 | `RENDER_JOBS` tanpa batas & thread tanpa batas | Rendah (DoS lokal) | Antrian job dengan batas paralel |
| S-07 | Error mentah (`str(e)`) dari ffmpeg/yt-dlp dikirim ke pengguna | Rendah | Log detail di server, pesan ramah di UI |
| S-08 | Kunci API berbayar dibaca dari `.env` dan dikirim ke API eksternal | Kebijakan | Di ekosistem ZOI: kosongkan & nonaktifkan |
| S-09 | `subprocess` memanggil ffmpeg dengan **list argumen** (bukan shell string) ✅ | — | Aman dari command injection |
| S-10 | Jinja `render_template_string` dengan autoescape ✅ | — | Judul/hook dari AI tetap ter-escape |

## 3. Blueprint Studio

| ID | Temuan | Tingkat | Rekomendasi |
|---|---|---|---|
| S-11 | `cards()` menulis nama/deskripsi gaya ke `innerHTML` tanpa escape; gaya buatan AI ikut masuk | Rendah–Sedang | Pakai `esc()` yang sudah ada |
| S-12 | Narasi & catatan visual sudah di-escape (`esc`) ✅ | — | |
| S-13 | Memuat Google Fonts → alamat IP terlihat oleh Google | Privasi rendah | Self-host font |
| S-14 | Prompt berisi topik & naskah dikirim ke Claude lewat `claude.use("sample")` | Privasi | Sudah wajar di claude.ai; di ZOI default ke Ollama lokal |

## 4. Desain keamanan ZOI (untuk Phase 1+)
1. **Bind lokal:** backend `127.0.0.1:8000`; mode LAN (akses dari HP) opsional dengan token sekali pakai + QR.
2. **OAuth Google:** alur resmi *installed app* (loopback redirect) + PKCE, scope minimum: `youtube.readonly`, `yt-analytics.readonly`, `yt-analytics-monetary.readonly` (hanya bila YPP). **Tidak pernah meminta password Google.**
3. **Penyimpanan kredensial:** refresh token di Windows Credential Manager via `keyring`; fallback file terenkripsi (`cryptography` Fernet). Tidak pernah dikirim ke frontend.
4. **Permission Manager agent:** setiap tool punya level (`read`, `write_local`, `network`, `publish`). Level `publish` (unggah ke YouTube) **selalu** butuh persetujuan manual — sesuai aturan "jangan publikasi tanpa persetujuan".
5. **Validasi input:** Pydantic di semua endpoint; whitelist domain URL.
6. **Cost guard jaringan:** daftar host yang diizinkan (lihat COST_CONTROL.md).
7. **Mikrofon:** rekaman diproses lokal (faster-whisper); Web Speech API Chrome hanya setelah persetujuan karena audio dikirim ke Google.
8. **Logging:** log rotasi lokal tanpa token/kunci; redaksi otomatis.
9. **Backup & recovery:** backup SQLite harian (`VACUUM INTO`), simpan 7 versi; backup otomatis sebelum migrasi Alembic.
10. **Supply chain:** kunci versi (`requirements.lock`, `package-lock.json`), `pip-audit` + `npm audit` di tes.
