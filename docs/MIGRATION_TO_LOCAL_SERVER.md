# Migrasi ZOI ke local server Windows

Target: ZOI berjalan di `http://127.0.0.1` pada komputer Windows 10/11, memakai Ollama lokal.
Tidak ada biaya layanan. Tidak ada langkah yang mengubah ZOI AI CLIPPER atau Blueprint Studio.

## 0. Yang dibutuhkan

| Kebutuhan | Keterangan |
|---|---|
| Windows 10/11 64-bit | |
| Python 3.12+ | python.org, centang "Add python.exe to PATH" |
| Ruang disk | ±0,3 GB untuk ZOI + cadangan 5 GB untuk Windows (diperiksa otomatis oleh `install.ps1`) |
| Ollama + 1 model lokal | **Opsional dan atas keputusanmu sendiri** — lihat langkah 5. Tanpa ini fitur AI berstatus "tidak tersedia" |
| Node.js | **Tidak perlu** — paket rilis sudah berisi frontend hasil build |

## 1. Siapkan paket

Di workspace pengembangan:

```bash
scripts/build_frontend.sh
backend/.venv/bin/python scripts/build_release.py   # → release/zoi-command-center-<versi>.zip
```

Salin ZIP ke local server dan ekstrak, misalnya ke `C:\ZOI\zoi-command-center`.

## 2. Ekspor data dari mesin lama (jika ada)

```bash
cd backend && python -m app.cli data export --exclude-mock --out zoi-pindah.zip
```

`--exclude-mock` membuang percakapan mock dari mode development agar tidak tercampur data asli.

## 3. Pasang

```powershell
cd C:\ZOI\zoi-command-center
powershell -ExecutionPolicy Bypass -File deploy\windows\install.ps1
```

Skrip memeriksa Python dan ruang disk **sebelum** memasang apa pun, lalu meminta persetujuan sebelum
mengunduh paket Python (±80 MB).

## 4. Isi `.env`

`install.ps1` membuat `.env` dari `.env.local.example`. Sesuaikan:

```ini
ZOI_MODE=local
ZOI_PORT=80
ZOI_OLLAMA_MODEL=          # isi setelah langkah 5
ZOI_CLIPPER_DIR=C:\ZOI\zoi-ai-clipper
ZOI_BLUEPRINT_FILE=C:\ZOI\blueprint-studio\Blueprint_Studio.html
```

Jika port 80 dipakai program lain (IIS, XAMPP, dll.), `doctor` menyebut programnya. ZOI tidak mematikan
program lain — pilih: hentikan program itu, atau set `ZOI_PORT=8000` (alamat menjadi `http://127.0.0.1:8000`).

## 5. (Opsional) Ollama dan model lokal

ZOI **tidak pernah** memasang Ollama atau mengunduh model. Bila hardware memadai (lihat
`docs/audit/HARDWARE_REQUIREMENTS.md`) dan kamu setuju dengan ukuran unduhannya:

1. Pasang Ollama dari ollama.com/download (gratis, open source). Bila disk C: sempit, atur `OLLAMA_MODELS`
   ke drive lain sebelum mengunduh model.
2. Unduh satu model lokal, misalnya `ollama pull qwen3:4b` (±2,5 GB) atau `qwen3:8b` (±5 GB).
   Jangan memakai model bertag `cloud` — ZOI menolaknya.
3. Isi `ZOI_OLLAMA_MODEL` di `.env` — atau pilih model nanti di **Settings › AI Lokal** (pilihan di sana
   tersimpan di database dan menimpa `.env`).

Ollama di komputer lain di jaringan rumah juga bisa: `ZOI_OLLAMA_URL=http://192.168.x.x:11434` dan tambahkan
`192.168.x.x` ke `ZOI_EXTRA_ALLOWED_HOSTS`.

## 6. Impor data (jika ada)

```powershell
cd backend
..\backend\.venv\Scripts\python.exe -m app.cli data import ..\zoi-pindah.zip
```

ZOI harus dalam keadaan berhenti. Data lama di-backup otomatis ke `data\backups\`.

## 7. Jalankan dan periksa

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\start.ps1 -OpenBrowser
```

Buka `http://127.0.0.1` lalu:

- [ ] Tidak ada pita kuning "DEVELOPMENT MODE"
- [ ] Status "Tersambung" di bilah atas
- [ ] Pill AI menampilkan nama model (atau "tidak tersedia" dengan alasan yang jelas bila Ollama belum ada)
- [ ] Task Manager → "Jalankan pemeriksaan sistem" → Selesai
- [ ] Overview menampilkan CLIPPER/Blueprint "ditemukan (read-only)" bila path diisi
- [ ] `python -m app.cli doctor --skip-port` tanpa baris FAIL
- [ ] (Bila Ollama dipasang) Settings › AI Lokal: versi Ollama, model terpasang, dan model aktif tampil;
      "Uji koneksi" berhasil; chat menjawab tanpa lencana MOCK; tombol **Berhenti** menghentikan jawaban
- [ ] (Bila Ollama dipasang) Jalankan **Uji model** sekali untuk model aktif dan nilai jawaban percakapannya.
      Ini pertama kalinya ZOI berbicara dengan Ollama sungguhan — semua tes sebelumnya memakai Ollama tiruan

Opsional: `deploy\windows\autostart.ps1` agar ZOI berjalan otomatis saat login.

## Catatan jujur

- Skrip PowerShell belum pernah dijalankan di Windows sungguhan (lingkungan pengembangan tidak memiliki
  PowerShell). Laporkan baris error apa pun saat migrasi; perbaikan dilakukan sebelum Phase 2 dianggap selesai.
- Kode backend dan frontend sudah diuji otomatis di Linux, termasuk E2E dalam mode local pada satu port.
