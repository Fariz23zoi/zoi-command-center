# ADR 0011 — AI cloud gratis opsional: NVIDIA NIM (utama) dan OpenRouter (cadangan)

**Status:** diterima (15 Nov 2026). **Mengubah aturan proyek atas keputusan pengguna:** "Gunakan Ollama dan model
lokal" dan LOCAL FIRST kini berbunyi *lokal sebagai bawaan; AI cloud gratis boleh dipilih pengguna*. ZERO PAID API
dan ZERO SUBSCRIPTION **tidak berubah**. Bytez tidak dipakai.

**Alasan.** Laptop pengguna (AMD E1-6010, ±7 GB RAM) terlalu lemah untuk menjalankan model lokal dengan nyaman.

**Keputusan pengguna.** K-1 semua konteks boleh dikirim (chat, memori, judul video, tema, naskah). K-2 penyedia
dan model dipilih lewat `.env` saja. K-3 bila NVIDIA gagal atau batasnya tercapai, pindah otomatis ke OpenRouter.

**Fakta yang dipakai** (dicek 15 Nov 2026; batas gratis bisa berubah sepihak):
- NVIDIA NIM: `https://integrate.api.nvidia.com/v1`, bentuk API seperti OpenAI, kunci `nvapi-…` (dokumentasi
  NVIDIA). ±40 permintaan/menit tanpa kartu kredit (situs pihak ketiga dan forum NVIDIA — belum ditemukan di halaman
  resmi). Sebagian model di daftar tidak bisa dipanggil akun pribadi (forum NVIDIA). Ketentuan uji coba NVIDIA
  **belum dibaca** oleh penulis ADR ini; pengguna diminta membacanya saat mendaftar.
- OpenRouter: model berakhiran `:free` dibatasi 20 permintaan/menit dan 50/hari selama akun belum pernah membeli
  kredit $10. Kebijakan pencatatan data model gratis **belum diverifikasi**.

**Rancangan.**
- **Bawaan tidak berubah:** tanpa `.env` baru, ZOI tetap Mock (development) atau Ollama (local) dan kedua host
  cloud tetap **diblokir** Cost Guard, walau ditambahkan ke `ZOI_EXTRA_ALLOWED_HOSTS`.
- **Mengaktifkan:** `ZOI_AI_PROVIDER=nvidia`, `ZOI_NVIDIA_MODEL=…`, opsional `ZOI_AI_FALLBACK=openrouter` +
  `ZOI_OPENROUTER_MODEL=…:free`. ZOI menolak mulai bila model kosong atau model OpenRouter bukan `:free`. Tidak ada
  nama model yang dikunci di kode (daftar model berubah cepat); halaman Settings › AI Cloud menyediakan daftar model
  dan tombol **Uji model**.
- **Penjaga biaya berlapis:** (1) hanya host penyedia yang dipilih yang dibuka; (2) hanya path `/chat/completions`
  dan `/models`; (3) model OpenRouter tanpa akhiran `:free` ditolak sebelum dikirim; (4) status 402 dilaporkan
  sebagai "meminta pembayaran" dan tidak pernah dicoba ulang; (5) hitungan permintaan ZOI sendiri berhenti di bawah
  batas gratis (NVIDIA 30/menit; OpenRouter 15/menit dan 45/hari, hitungan harian disimpan di database).
- **API key** dimasukkan lewat UI dan disimpan di keyring sistem (Windows Credential Manager) — bukan di `.env`,
  repo, database, log, atau respons API. Folder `secrets` tidak ikut ekspor data.
- **Satu penghubung** bergaya OpenAI lewat httpx (tanpa dependensi baru): streaming SSE, pemisahan
  `reasoning_content`, perakitan `tool_calls` dari potongan, statistik token bila dikirim penyedia. Aliran yang
  berakhir tanpa penanda selesai dianggap terputus (error), bukan jawaban lengkap.
- **Keluaran terstruktur:** `response_format` tidak dipakai (dukungannya berbeda antar-model). Skema JSON dikirim
  sebagai teks, lalu hasil divalidasi Pydantic dengan satu percobaan ulang — sama seperti jalur lokal.
- **Cadangan:** pindah hanya bila penyedia utama gagal **sebelum** mengirim apa pun karena batas (429 atau batas
  aman ZOI), galat server, tidak terjangkau, atau waktu habis. Tidak pindah untuk API key salah, model tidak bisa
  dipanggil, permintaan ditolak, atau jawaban yang sudah separuh tampil. Jawaban cadangan mengubah label pesan/draf
  menjadi penyedia yang sebenarnya menjawab dan menyimpan alasannya (`messages.note`, migrasi 0006).
- **Label:** setiap jawaban cloud diberi "AI cloud · penyedia · model". Peringatan "AI CLOUD aktif" muncul di log
  dan konfigurasi. Halaman Settings › AI Cloud menampilkan daftar data yang dikirim dan yang tidak pernah dikirim.
- **Suara tetap lokal** (Whisper/Piper); tidak ada rekaman yang dikirim ke cloud.
- **Pengujian:** `ZOI_CLOUD_TEST_URL` (hanya loopback) mengarahkan kedua penyedia ke `tests/fake_cloud.py`; UI
  menampilkan "ENDPOINT UJI".

**Konsekuensi.**
- Saat aktif, isi percakapan dan konteks meninggalkan komputer pengguna. Itu pilihan pengguna, bisa dibatalkan
  dengan menghapus baris `.env`.
- Label pada **permintaan agen** mengikuti penyedia utama; bila cadangan menjawab di tengah tugas agen, alasannya
  tidak tercatat per langkah (hanya chat dan draf konten yang mencatatnya).
- Uji model 20-prompt (Phase 3) tetap khusus Ollama; untuk cloud tersedia uji satu permintaan.
- Seluruh jalur diuji terhadap server tiruan. Koneksi pertama ke NVIDIA/OpenRouter sungguhan terjadi di komputer
  pengguna; bentuk respons asli (terutama `tool_calls` dan `reasoning_content`) bisa berbeda per model.
- Cadangan OpenRouter kecil (45/hari); tugas agen yang panjang bisa menghabiskannya.
