# REDESIGN_ROADMAP — ZOI Universe V2

Pemulihan: `git checkout checkpoint/pre-redesign` (branch di GitHub) — kode v1.1.1 persis sebelum redesign.
Semua pekerjaan redesign di branch `redesign/v2`; `main` baru diubah setelah Phase 7 lolos.

| Phase | Isi | Selesai bila |
|---|---|---|
| 1 Audit | UI_AUDIT, ARCHITECTURE, roadmap ini, checkpoint | ✅ |
| 2 Design system | `packages/ui`: tokens warna spesifikasi, tipografi, Button/Card/Sidebar/Drawer/Badge/StatusDot, `prefers-reduced-motion` | typecheck + lint + vitest hijau |
| 3 ZOI Universe | UniverseShell, Landing (hero + bola partikel ringan CSS/canvas, bukan three.js), About, Products (+ halaman produk), Projects, Technology, Contact, Dashboard (data nyata), Account; halaman lama pindah ke `/app/*` + redirect | E2E lama tetap hijau + E2E baru navigasi |
| 4 ZOI AI Workspace | AgentShell `/ai`: sidebar (New chat, riwayat, Models, Agents, Tools, Memory, Settings, Back), chat streaming + markdown + highlight + copy, hapus chat (endpoint baru), suara, panel kanan opsional, greeting & saran; avatar 3D orisinal + fallback 2D | E2E chat/agent/voice/avatar hijau |
| 5 Integrasi | Tombol "Open ZOI AI", navigasi silang, registry produk, sesi tunggal (mode online) | E2E auth online |
| 6 Optimasi | Bundle budget (landing < 200 KB gz tanpa three), FPS cap, lazy, Lighthouse mobile | ukuran build tercatat |
| 7 Testing | Semua pytest/vitest/Playwright + uji mobile 375 px tanpa overflow | semua hijau |
| 8 Finalisasi | Dokumen, ADR 0016, rilis 1.2.0 ZIP diuji install bersih | ZIP terverifikasi |

## Bagian spesifikasi yang bertentangan dengan aturan proyek (perlu keputusan)
1. **OpenAI & Anthropic Claude API berbayar** (pay-as-you-go) → bertentangan dengan ZERO PAID API. Rencana: tidak dibuat, kecuali disetujui.
2. **Google Gemini & Bytez**: status tier gratis belum diverifikasi — dicek sebelum dibangun; hanya dipasang bila benar-benar gratis tanpa kartu.
3. **Custom OpenAI-compatible API**: aman (mis. LM Studio/llama.cpp lokal), direncanakan dibangun.
4. **Contact page**: tidak ada data kontak nyata → butuh email/link dari pemilik; tidak dibuat formulir palsu.
5. **ZOI AI LAB**: belum ada produknya → ditampilkan berstatus "Planned", tanpa tombol Open palsu.
6. **ZOI AI CLIPPER**: tetap status "Ditunda" (alasan ketentuan YouTube); kartu produk jujur.
7. Bahasa UI: spesifikasi berbahasa Inggris (landing, greeting) — dipakai sesuai spesifikasi; halaman fungsi tetap Bahasa Indonesia kecuali diminta lain.

## Keputusan pemilik (16 Nov 2026)
- Provider: **hanya gratis** — NVIDIA NIM, OpenRouter `:free`, Ollama, Custom OpenAI-compatible; Gemini/Bytez hanya bila terverifikasi gratis tanpa kartu. OpenAI/Claude tidak dibuat.
- Contact: **link GitHub Fariz23zoi saja**, tanpa formulir/email.
- Avatar 3D: **React Three Fiber + Drei disetujui** (MIT), lazy di workspace AI.

## Arah visual dari pemilik (16 Nov 2026) — referensi di `reference/`
**Dashboard (`dashboard-ref.png`)**: sidebar ungu gelap berkelompok (Analytics / Creation / Products), banner sambutan + tombol alur (Analisis Channel → Riset Tren → Ide Konten → Buat Video), 4 kartu statistik, grafik performa bertab, Sumber Traffic (donut), Perangkat Penonton, Video Terbaik, Insight AI, Tren Topik, badge "Mode: Local" + "AI Terhubung".
Aturan penerapan:
- Semua angka dari YouTube Analytics/Data API milik pengguna; belum terhubung → kartu kosong + tombol "Hubungkan YouTube". **Tidak ada angka contoh.**
- Tab/kartu yang tidak disediakan API resmi tidak ditampilkan (dicek saat implementasi, mis. CTR).
- Insight AI = teks dari AI berdasarkan angka nyata, diberi label "dibuat AI".
- Ilustrasi karakter & pemandangan di gambar tidak dipakai (lisensi tidak jelas) → diganti avatar ZOI 3D sendiri + latar abstrak.

**Workspace AI (`office-ref.jpg`)**: avatar ZOI hidup di **kantor isometrik 3D low-poly** (R3F): meja kerja, phone booth, ruang rapat, pojok perpustakaan, lounge. Posisi/aktivitas avatar mengikuti status nyata:
| Status ZOI | Zona & aktivitas |
|---|---|
| idle | lounge / berjalan santai |
| listening | phone booth (mendengar mikrofon) |
| thinking / agen menyusun rencana | meja kerja, mengetik |
| tool berjalan / tugas latar | papan tugas / printer, sesuai jenis tugas |
| speaking | ruang rapat menghadap kamera |
| riset / memori | pojok perpustakaan |
Performa: geometri sederhana + instancing, tanpa tekstur besar, FPS maks 30, render berhenti saat tab tersembunyi, kamera tetap isometrik. Mobile / FPS rendah → mode ringan (avatar close-up) atau fallback 2D.

## Status akhir (16 Nov 2026) — rilis 1.2.0
Phase 1–8 selesai. Yang sengaja belum dibuat (tercatat jujur):
- Provider Gemini/Bytez & "Custom OpenAI-compatible" — belum; butuh verifikasi tier gratis & UI kelola provider. Sistem provider tetap NVIDIA NIM / OpenRouter :free / Ollama lewat `.env`.
- Attachment di chat, usage tracking per provider, lip-sync robot kantor (lip-sync tetap ada di avatar close-up).
- Insight AI & Tren Topik di dashboard (butuh label "Estimasi AI"); tersedia di halaman Trend Detector / Content Ideas.
- Login multi-pengguna: ZOI tetap satu pemilik.

## 1.2.1 (17 Nov 2026)
- **Keputusan pemilik**: tombol Open ZOI AI CLIPPER menyalakan web app CLIPPER apa adanya (`python app.py`, port 5000) sebagai proses terpisah dan membukanya di tab baru. ZOI tidak mengimpor/mengubah repo CLIPPER dan tidak mengunduh video; pemakaian fitur yt-dlp di CLIPPER tanggung jawab pemilik. API: `/api/clipper/{status,start,stop}` (hanya mode local).
- `index.html` dikirim dengan `Cache-Control: no-cache` agar update langsung terlihat tanpa hapus cache.
- Catatan: CLIPPER sendiri mendengarkan di `0.0.0.0:5000` (terjangkau perangkat lain di jaringan yang sama) — perilaku bawaan CLIPPER, tidak diubah.
- 1.2.2: halaman Blueprint Studio punya tombol **Buka Blueprint Studio** (membuat/memperbarui salinan lalu membuka `/blueprint-studio/`).
