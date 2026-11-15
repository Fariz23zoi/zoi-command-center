# ADR 0010 — Data publik YouTube ≤30 hari tanpa skor; tema, ide, dan naskah sebagai draf AI lokal

**Status:** diterima (15 Nov 2026). Melaksanakan keputusan pengguna K-2 (Phase 6): fitur kompetitor/viral/tren
**dirancang ulang agar patuh** kebijakan YouTube.

**Fakta yang dipakai** (halaman resmi, dicek 14–15 Nov 2026):
- Kebijakan Developer YouTube: statistik non-berizin tidak boleh disimpan >30 hari (III.E.4.d); dilarang membuat
  metrik turunan dari data API (III.E.4.h); data API tidak boleh diagregasi lintas channel (III.E.2.b).
- Sejak 1 Jun 2026 `search.list` punya ember kuota sendiri: 100 panggilan/hari, 1 per panggilan, terpisah dari
  10.000 unit umum. `videos.list`, `channels.list`, `playlistItems.list`, `videoCategories.list` = 1 unit.

**Keputusan.**
- **Satu tabel `youtube_public_cache`** untuk semua data publik (channel pantauan, Trending, hasil pencarian,
  kategori, rangkuman tema). Baris yang lebih tua dari 30 hari dihapus saat aplikasi mulai dan setiap kali data
  dibaca. Tidak ada riwayat/snapshot data publik. Setiap tampilan memuat sumber, waktu ambil, dan waktu hapus.
- **Daftar pantauan** hanya menyimpan ID channel + catatan pengguna (maks. 20). Nama dan angka channel hanya ada
  di cache; setelah 30 hari yang tersisa ID dan catatan.
- **Tanpa skor/peringkat buatan ZOI.** Trending = `videos.list chart=mostPopular regionCode=ID` dan pencarian =
  `search.list`, ditampilkan dalam urutan dari YouTube. Angka yang tidak dikirim YouTube tampil "—". Tidak ada
  "kecepatan naik", "engagement rate", atau perbandingan antar-channel.
- **Kuota:** pencarian dihitung di ember sendiri (berhenti di 90) dan tidak memotong unit umum.
- **Saat akun diputuskan**, cache publik dan daftar pantauan ikut dihapus (datanya diambil dengan izin akun itu).
- **Trend Detector = interpretasi teks.** AI lokal hanya menerima **judul** dari satu daftar tersimpan (maks. 50),
  di blok DATA yang dinyatakan bukan instruksi; tidak ada angka yang dikirim. Hasilnya tema + penjelasan + contoh
  judul. Contoh yang tidak ada di daftar dibuang dan jumlahnya ditampilkan. Rangkuman diberi label "interpretasi AI,
  bukan statistik", disimpan di cache publik (ikut aturan 30 hari), dan dihapus bersama daftarnya.
- **Ide dan naskah** adalah draf AI lokal (`content_items`), selalu memuat penyedia/model. Konteks ide: memori +
  judul video channel sendiri (tanpa angka) + tema bila dipilih. Prompt melarang mengarang statistik dan meminta
  penanda "[perlu riset: …]". Mock memakai teks tertulis berlabel [MOCK] dan halaman menampilkan pita MOCK.
  Hasil kosong dilaporkan sebagai gagal. Tidak ada kolom atau endpoint publikasi.
- **AI berjalan sebagai tugas Task Manager** di jalur antrean `content` (batas 15 menit) — laptop lemah bisa butuh
  beberapa menit, dan permintaan HTTP tidak ditahan.
- **Performance** memakai laporan YouTube Analytics per video (`dimensions=video`) untuk channel sendiri, termasuk
  `averageViewPercentage` yang dihitung YouTube. "Waktu upload terbaik" **tidak dibuat**: API tidak menyediakan
  laporan aktivitas penonton, dan menebaknya dari angka lain adalah metrik turunan. Halaman menunjuk ke YouTube
  Studio.

**Yang sengaja tidak ada.** Scraping, thumbnail dari host luar, skor viral, grafik pertumbuhan kompetitor, riwayat
kompetitor, tool agen untuk data publik (belum diminta), subtitle/timing presisi (Phase 7).

**Konsekuensi.**
- "Viral Video Hunter" dan "Trend Detector" lebih sederhana daripada nama dan rencana awalnya: daftar resmi dan
  rangkuman judul, bukan deteksi otomatis.
- Kualitas tema, ide, dan naskah bergantung pada model lokal; diuji dengan Mock dan Ollama tiruan saja.
- Halaman ini bukan nasihat hukum; kebijakan YouTube bisa berubah. Aturan penyimpanan terpusat di
  `app/youtube/public.py` (`RETENTION_DAYS`).
