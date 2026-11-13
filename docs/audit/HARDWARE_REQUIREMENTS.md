# HARDWARE_REQUIREMENTS.md — Revisi 2 (berdasarkan laptop pengguna)

Tanggal: 14 November 2026 · Menggantikan revisi 1 (yang menjadikan Qwen3 8B sebagai default — **dibatalkan**).
Label: **FACT** = data resmi/terverifikasi · **ESTIMATE** = perkiraan dengan metode tertulis · **HYPOTHESIS** = harus diuji di laptop.

---

## 1. Spesifikasi laptop (dari pengguna + data resmi)

| Komponen | Nilai | Sumber |
|---|---|---|
| CPU | AMD E1-6010 APU ("Beema", April 2014): **2 core / 2 thread, 1,35 GHz, tanpa boost**, TDP 10 W | FACT — Notebookcheck |
| Instruksi CPU | SSE hingga 4.2, **AVX (AVX1)**, AES, F16C — **tanpa AVX2, tanpa FMA3** | FACT — Notebookcheck, TechPowerUp |
| Memori | ±7 GB terpakai sistem (kemungkinan 8 GB fisik, sebagian dibagi ke GPU). Kontroler **single-channel DDR3L-1333** → bandwidth teoretis ±10,6 GB/s | FACT (kontroler) · ESTIMATE (bandwidth) |
| GPU | AMD Radeon R2: 128 shader GCN, 260–350 MHz, memori dibagi dengan RAM | FACT |
| Disk C: | **8,21 GB kosong** | FACT (pengguna) |
| CPU dapat di-upgrade? | **Tidak** — chip disolder (BGA, socket FT3) | FACT |
| Kelas performa | Notebookcheck: hanya layak untuk Office, browsing ringan, multimedia | FACT |

**Yang belum diketahui** (diperlukan untuk saran upgrade spesifik): merek & tipe laptop, jenis disk (HDD/SSD/eMMC) dan kapasitas total, adakah drive D:/slot kartu SD, versi Windows.

---

## 2. Kesimpulan kelayakan

| Komponen ZOI | Layak di laptop ini? | Alasan |
|---|---|---|
| Backend FastAPI + SQLite | ✅ Ya | ±80–120 MB RAM (ESTIMATE) |
| Dashboard web (frontend yang sudah di-*build*) | ✅ Ya | Satu tab browser |
| Data YouTube (API resmi), analitik, monetisasi, task, memory, automation | ✅ Ya | Komputasi ringan, beban utamanya jaringan |
| Avatar **2D** (SVG/CSS) yang mengikuti status | ✅ Ya — **default** | Hampir tanpa beban GPU |
| Avatar **3D Lite** (1 model < 1 MB, tanpa bayangan) | ⚠️ Opsional | Radeon R2 sangat lemah; wajib lolos uji FPS otomatis |
| TTS Piper (suara *low/medium*) | ⚠️ Opsional, HYPOTHESIS | Piper ringan, tetapi CPU ini sangat lambat → uji dulu |
| STT faster-whisper `tiny`/`base` | ⚠️ Opsional, HYPOTHESIS | Mungkin mendekati real-time untuk `tiny`; akurasi Bahasa Indonesia `tiny` rendah |
| **LLM lokal (Ollama)** | ❌ **Tidak layak untuk agent** | Lihat 2.1 |
| Render CLIPPER (FFmpeg + OpenCV) | ⚠️ Lambat tetapi bisa | ESTIMATE: beberapa menit hingga >15 menit per klip 60 detik; CLIPPER tidak diubah |
| Render HyperFrames (Node + Chrome headless + FFmpeg) | ❌ Tidak direkomendasikan di laptop ini | Disk ±1 GB tambahan + render sangat lambat |

### 2.1 Mengapa LLM lokal tidak layak di laptop ini
1. **Disk:** dokumentasi resmi Ollama untuk Windows meminta **minimal 4 GB hanya untuk instalasi program**, belum termasuk model. Dengan sisa 8,21 GB, Windows harus tetap punya cadangan untuk pembaruan. Kesimpulan: Ollama **tidak boleh** dipasang di C:.
2. **CPU:** inferensi LLM di CPU paling cepat memakai AVX2/FMA; E1-6010 hanya punya AVX1 dan 2 core 1,35 GHz. Sejumlah panduan menyebut AVX2 sebagai syarat minimum CPU Ollama. Runtime llama.cpp masih bisa berjalan tanpa AVX2, tetapi jauh lebih lambat.
3. **Kecepatan (ESTIMATE, metode: bandwidth memori ÷ ukuran bobot, lalu dikoreksi oleh keterbatasan komputasi):**

| Model (Q4) | Ukuran bobot | Kecepatan menulis jawaban | Memproses prompt agent (±1.500 token: instruksi + daftar tools) |
|---|---|---|---|
| ±0,3–0,6 B | 0,3–0,5 GB | ±2–6 token/detik | ±1–3 menit sebelum kata pertama muncul |
| ±1,7 B | ±1,1 GB | ±1–3 token/detik | ±3–8 menit |
| 4 B ke atas | ≥2,5 GB | <1 token/detik | >10 menit — tidak praktis |

Model sekecil itu juga lemah untuk tool calling dan Bahasa Indonesia. **Keputusan: AI lokal = OPSIONAL & NONAKTIF secara default di laptop ini.** Angka di atas ESTIMATE; benchmark nyata hanya dilakukan bila kamu menyetujuinya dan menyediakan ruang di drive lain.

---

## 3. Anggaran disk ZOI Lite (diperiksa sebelum instalasi apa pun)

| Item | Ukuran (ESTIMATE) | Wajib? |
|---|---|---|
| Python 3.12 (tanpa Tcl/Tk, docs, test suite) | ±100 MB | Ya (lewati jika sudah ada — cek `py --version`) |
| venv ZOI (fastapi, uvicorn, sqlalchemy, alembic, pydantic, httpx, psutil, structlog) | ±60–80 MB | Ya |
| Kode ZOI + frontend siap pakai (sudah di-*build*) | ±10 MB | Ya |
| Avatar 2D | <1 MB | Ya |
| Database SQLite + log + 7 backup (dibatasi rotasi) | maks. 200 MB | Ya |
| **Total ZOI Lite inti** | **±0,4 GB** | |
| Avatar 3D Lite (Rocketbox .glb + viseme model) | ±2 MB | Opsional |
| Piper + 1 suara | ±150 MB | Opsional |
| faster-whisper + model `tiny` (`base`) | ±200 MB (±270 MB) | Opsional |
| Node.js, Git, browser Playwright | **0 MB di laptop** — build & tes dilakukan di workspace cloud; laptop menerima hasil jadi | — |
| Ollama + model terkecil | ≥4,5 GB | **Tidak di C:** |

**Aturan cadangan disk:** skrip instalasi menolak lanjut jika sisa ruang C: setelah instalasi **di bawah 5 GB** (cadangan untuk Windows Update & file sementara). Perhitungan: 8,21 − 0,4 (inti) = ±7,8 GB → **aman untuk inti**. Dengan semua modul opsional: 8,21 − 0,8 = ±7,4 GB → masih aman.

**Catatan video:** satu video sumber 720p untuk CLIPPER bisa 50–300 MB, dan hasil render menambah lagi. Di C: hanya muat beberapa video. Simpan data video di drive lain (USB/SD) bila memungkinkan; ZOI bisa menaruh folder datanya di drive lain lewat Settings tanpa mengubah CLIPPER.

---

## 4. Anggaran RAM ZOI Lite (ESTIMATE)

| Proses | RAM |
|---|---|
| Windows + layanan dasar | 2,5–3,5 GB |
| Backend ZOI (1 worker) | 0,1 GB |
| Browser, 1 tab ZOI (avatar 2D) | 0,2–0,4 GB |
| + Avatar 3D Lite | +0,1–0,2 GB |
| + Piper saat bicara | +0,1 GB |
| + faster-whisper `tiny` saat mendengar | +0,3 GB |
| **Total puncak** | **±3,5–4,5 GB dari ±7 GB** ✅ |

Saran: jalankan ZOI di Edge dengan *Efficiency mode* atau Firefox, tutup tab lain. Jangan menjalankan render CLIPPER bersamaan dengan voice.

---

## 5. Spesifikasi minimum per edisi ZOI

| Edisi | Untuk siapa | CPU | RAM | Disk kosong | GPU |
|---|---|---|---|---|---|
| **ZOI Lite** (laptop ini) | Dashboard, data YouTube, task, memory, automation, avatar 2D/3D Lite, asisten perintah tanpa AI generatif | 2 core x86-64 | 4 GB (6+ disarankan) | 1 GB + cadangan 5 GB | WebGL opsional |
| **ZOI Standard** | + LLM lokal 4B, voice lancar | 4 core / 8 thread **dengan AVX2** (Intel gen-8+ / Ryzen 3000+) | 16 GB | 40 GB SSD | Terintegrasi modern |
| **ZOI Full** | + LLM 8B, avatar 3D penuh, render cepat | 6+ core AVX2 | 16–32 GB | 60 GB SSD | NVIDIA 6–8 GB VRAM |

---

## 6. Rekomendasi upgrade (dari termurah)

| # | Langkah | Biaya | Dampak |
|---|---|---|---|
| U-1 | **Bersihkan C:** Disk Cleanup → "Clean up system files", Storage Sense, hapus berkas *Downloads*/sementara lama. Opsi lanjutan (keputusanmu, karena mengubah setelan sistem): matikan hibernasi `powercfg /h off` → biasanya membebaskan beberapa GB | Gratis | Ruang C: lebih aman |
| U-2 | **Flashdisk/microSD 64–128 GB** khusus folder data ZOI & video | Murah | Video & model tidak membebani C: |
| U-3 | **Ganti disk ke SSD SATA 240–480 GB** — *jika* laptop punya bay 2,5" (banyak laptop E1-6010 punya; ada juga yang memakai eMMC yang tidak bisa diganti) | Sedang | Booting & aplikasi jauh lebih responsif, disk tidak lagi jadi masalah. **CPU tetap lambat** |
| U-4 | RAM | — | Kontroler single-channel; ±7–8 GB kemungkinan sudah maksimum praktis (HYPOTHESIS — cek tipe laptop). **Tidak disarankan** keluar uang di sini |
| U-5 | **Komputer kedua untuk AI** (bekas pun cukup): CPU 4 core dengan AVX2, RAM 16 GB, SSD 256 GB. Pasang Ollama di sana; laptop ini tetap menjalankan ZOI Lite dan memakai AI lewat jaringan rumah (gratis, tetap lokal) | Terbesar | Membuka AI lokal tanpa mengganti laptop |
| U-6 | Ganti laptop ke kelas ZOI Standard | Terbesar | Semua fitur di satu perangkat |

CPU tidak bisa di-upgrade karena chip disolder ke motherboard.

---

## 7. Yang perlu kamu kirim untuk melengkapi analisis
Jalankan di PowerShell (hanya membaca, tidak mengubah apa pun):
```powershell
Get-CimInstance Win32_ComputerSystem | Select Manufacturer,Model
Get-PhysicalDisk | Select FriendlyName,MediaType,BusType,@{n='Size_GB';e={[math]::Round($_.Size/1GB)}}
Get-PSDrive -PSProvider FileSystem | Select Name,@{n='Free_GB';e={[math]::Round($_.Free/1GB,1)}}
(Get-CimInstance Win32_OperatingSystem).Caption
Get-CimInstance Win32_PhysicalMemory | Select Capacity,Speed
py --version
```
