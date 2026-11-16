# ADR 0008 — Agen atas permintaan, rencana disetujui dulu, memori FTS5, tanpa tool publikasi

**Status:** diterima (14 Nov 2026). Keputusan pengguna: K-1 agen **atas permintaan** (tombol Rencanakan / `/agen`),
K-2 **rencana ditampilkan dan disetujui dulu**, K-3 memori dicari dengan **SQLite FTS5** (tanpa unduhan).

**Keputusan.**
- **Perencana** memakai `chat_json` dengan skema `Rencana` (tujuan + maks. 6 langkah `{tool, argumen, alasan}`).
  Setiap langkah divalidasi terhadap registry: tool harus ada, argumen harus lolos skema Pydantic tool tersebut.
  Rencana tidak valid ditampilkan beserta alasannya dan tidak bisa dijalankan. Mock memakai rencana tertulis
  berlabel MOCK (tanpa angka) agar seluruh alur bisa diuji di development.
- **Registry tool** dengan tiga tingkat izin: `read` (otomatis setelah rencana disetujui), `write_local` (izin per
  langkah, bisa diizinkan otomatis per tool), `external` (selalu izin; dipakai mulai Phase 6). **Tidak ada tingkat
  publikasi.** Registry menolak nama yang mengarah ke publikasi (publish, upload, unggah, posting, kirim pesan, …).
- **Tool awal hanya kemampuan yang benar-benar ada:** waktu, cari/simpan/ubah/hapus memori, status sistem,
  pemeriksaan sistem, status AI, status CLIPPER/Blueprint (read-only), daftar tugas.
- **Eksekutor** adalah tugas Task Manager (`agent_run`) di **jalur antrean sendiri** — agen yang menunggu izin
  tidak menahan tugas lain. Satu permintaan agen aktif pada satu waktu. Langkah gagal, izin ditolak, atau izin
  kedaluwarsa (10 menit) menghentikan sisa langkah. Setelah restart, permintaan yang terputus ditandai gagal.
- **Penilai hasil:** ringkasan akhir dibuat AI hanya dari keluaran tool (ditandai DATA); angka di ringkasan yang
  tidak muncul di keluaran tool/permintaan diberi peringatan ⚠️. Mock tidak membuat ringkasan berangka.
- **Memori:** tabel `memories` + indeks FTS5 *external content* yang dijaga trigger (dibuat dengan SQL mentah di
  migrasi 0003, sengaja di luar model ORM). Kueri pengguna disanitasi (tiap kata dikutip, awalan, OR). Maks. 5
  memori relevan disisipkan ke prompt chat & perencana sebagai blok DATA yang menyatakan dirinya bukan instruksi.
  Agen hanya menyimpan memori lewat `simpan_memori` (`write_local` → izin).
- Permintaan & ringkasan agen menjadi pesan di percakapan (`messages.agent_run_id`), sehingga muncul di riwayat dan
  dibacakan bila "Bacakan jawaban" aktif.

**Bug yang ditemukan saat E2E dan diperbaiki.**
- `approve()` dulu mengubah status menjadi "running" *setelah* tugas dikirim; langkah Mock yang cepat sudah mencapai
  "waiting_approval" lalu tertimpa → kartu izin tidak pernah muncul. Sekarang status diubah sebelum tugas dikirim,
  dan browser mengabaikan versi permintaan agen yang lebih lama dari yang sudah diterima lewat WebSocket.
- Task Manager punya satu pekerja; agen yang menunggu izin menahan pemeriksaan sistem hingga 10 menit. Sekarang
  setiap jenis tugas bisa punya jalur antrean sendiri.

**Konsekuensi.** Kualitas rencana bergantung pada model lokal — belum diuji dengan model sungguhan (Ollama tiruan).
