# ADR 0003 — Mock Provider dengan batas ketat

**Status:** diterima (14 Nov 2026)

**Konteks.** Model AI lokal belum tersedia, tetapi alur chat/agent harus bisa dibangun dan diuji. Aturan
proyek melarang data palsu yang tampak nyata.

**Keputusan.**
1. Mock hanya ada di mode development; mode local menolak start bila `ZOI_AI_PROVIDER=mock` dan tidak pernah
   jatuh diam-diam ke mock bila Ollama mati.
2. Setiap jawaban diawali `[MOCK]`, diberi lencana MOCK di UI, dan disimpan dengan `is_mock=true`.
3. Mock tidak pernah menghasilkan angka/statistik (skenario JSON dilarang berisi digit — dijaga tes).
4. Mock dan Ollama lulus **contract test yang sama** (streaming, error, timeout, tool call, tool call rusak).
5. Ekspor untuk migrasi memakai `--exclude-mock`.
