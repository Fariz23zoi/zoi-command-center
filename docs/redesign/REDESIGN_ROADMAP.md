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
