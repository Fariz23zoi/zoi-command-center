# Pemeriksaan keamanan & kesehatan (Phase 9)

Jalankan sebelum merilis. Semua alat gratis dan open source; tidak ada yang mengirim kode ke layanan luar
kecuali basis data kerentanan publik (PyPI/OSV untuk pip-audit, registry npm untuk npm audit).

| Pemeriksaan | Perintah | Hasil 16 Nov 2026 |
|---|---|---|
| Kerentanan paket Python | `cd backend && .venv/bin/pip-audit -r requirements.txt` | 0 kerentanan |
| Kerentanan paket npm | `cd frontend && npm audit` | 0 (setelah `overrides.minimatch` ^11.0.8 — temuan ReDoS GHSA-g3hv-75wg-m249 hanya di alat lint) |
| Rahasia di file & riwayat Git | `python scripts/scan_secrets.py` | 0 temuan (312 file + seluruh riwayat) |
| Lisensi | `python scripts/check_licenses.py` | 101 paket diizinkan |
| Tes backend + cakupan | `cd backend && .venv/bin/python -m coverage run --source=app -m pytest && .venv/bin/python -m coverage report` | 385 lulus (termasuk 2 uji nyata Blueprint & HyperFrames), cakupan 93% |
| Tes frontend | `cd frontend && npm test` | 106 lulus |
| E2E (termasuk sapuan 19 halaman di layar HP 375 px) | `cd frontend && E2E_CHROME=<chrome> npx playwright test` | 105 lulus |

## Catatan

- **gitleaks** tidak dijalankan di workspace pengembangan (menjalankan biner unduhan diblokir di sana);
  `scripts/scan_secrets.py` memeriksa pola yang relevan untuk ZOI (NVIDIA, OpenRouter, Google OAuth, GitHub,
  Postgres/Neon, kunci privat). Kamu bisa menjalankan gitleaks sendiri: `gitleaks git .`.
- **Memori mode online** (Postgres lokal, 300 memori + pencarian + 3 unduhan cadangan + halaman): puncak RSS
  ±155 MB dari batas 512 MB Render free. Whisper/Piper/HyperFrames tidak pernah dimuat di mode online.
- **Ukuran frontend**: bundel utama ±120 KB gzip; avatar 3D (Three.js, ±276 KB gzip) dimuat terpisah hanya
  bila mode 3D dipakai.
- **Header (mode online)**: CSP ketat, `X-Content-Type-Options`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`, `Strict-Transport-Security`, dan `Cache-Control: no-store` untuk semua `/api/*`.
- **Batas login**: 10 percobaan gagal / 15 menit untuk semua alamat. Orang lain yang menebak-nebak bisa
  menahan login-mu sementara; buka kembali dengan **Setup token** (mengganti kata sandi juga menghapus hitungan).
