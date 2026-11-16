# OPEN_SOURCE_INTEGRATION_PLAN.md — Phase 0

Cara setiap komponen open-source masuk ke ZOI: **sebagai paket resmi (npm/pip/installer), bukan clone repo**, kecuali disebut lain.

| Komponen | Cara masuk | Fase | Yang dipakai | Yang TIDAK dipakai |
|---|---|---|---|---|
| three.js | npm `three` | 2 | renderer, GLTFLoader, meshopt decoder | contoh/editor |
| React Three Fiber | npm `@react-three/fiber` | 2 | Canvas, hooks | — |
| drei | npm `@react-three/drei` | 2 | `useGLTF`, `Environment`, `OrbitControls` (dibatasi) | sisanya (tree-shaken) |
| talking-avatar | npm `@interviewflowai/talking-avatar` | 2 | lip-sync dari audio, avatar Rocketbox | memuat model dari jsDelivr → **self-host** `viseme-model.bin` & `.glb` di `public/` |
| Ollama | installer Windows resmi (pengguna memasang sendiri) | 3 | HTTP API `/api/chat`, `/api/tags`, `/api/ps` | model `:cloud`, akun ollama.com |
| Qwen3 / Gemma 4 | `ollama pull` **setelah persetujuan** | 3 | 1 model default | unduh otomatis |
| faster-whisper | pip `faster-whisper` | 4 | transkripsi + word timestamps | — |
| Piper | pip `piper-tts` (proses terpisah) + 1 suara `id_ID` (cek MODEL_CARD) | 4 | TTS lokal | suara tanpa lisensi jelas |
| yt-dlp | pip (sudah di CLIPPER) | 6–7 | metadata & unduh atas perintah | scraping massal |
| google-api-python-client + google-auth-oauthlib | pip | 6 | Data API v3, Analytics API, OAuth loopback | — |
| FFmpeg | installer biner (pengguna) | 7 | render | — |
| HyperFrames | `npx hyperframes` di folder paket (Node ≥22) | 7 | render MP4 Blueprint | — |
| APScheduler | pip | 8 | automation | — |
| yt-analytics-hub | **tidak dipasang** | 6 | dibaca sebagai referensi pola cache & skema (MIT, atribusi di NOTICES bila ada potongan kode) | seluruh repo |
| YouTube-Dashboard | **tidak dipakai** | — | ide fitur saja (tanpa LICENSE) | kode |
| riverbornai avatar agent | **tidak dipakai** | — | — | semua (API berbayar, avatar RPM) |
| givemotion | **tidak dipakai sekarang** | — | dievaluasi ulang bila HyperFrames tidak cocok | — |
| Remotion | tidak dipasang | — | tetap sebagai opsi di Blueprint dengan catatan lisensi | default |

## Identitas visual ZOI (avatar)
Tahap 1 (Phase 2): avatar Rocketbox female/male bawaan (MIT) dengan material/warna futuristik ZOI (aksen ungu `#9385ff` dari CLIPPER), latar command center.
Tahap 2 (opsional, setelah disetujui): karakter ZOI orisinal — dibuat di VRoid Studio (gratis) atau Blender (GPL, aset hasil milikmu), diekspor `.glb` dengan 15 viseme Oculus + blendshape ARKit agar tetap kompatibel dengan talking-avatar. Animasi tubuh (idle, menunjuk, sukses) hanya bila model ber-rig + klip animasi berlisensi jelas.

## Kriteria adopsi (dipakai lagi setiap menambah dependency)
1. Lisensi OSI/permisif atau GPL yang terisolasi sebagai proses.
2. Tidak butuh API key berbayar untuk fungsi inti.
3. Rilis/commit dalam 12 bulan terakhir.
4. Jalan di Windows.
5. Bisa offline setelah instalasi.
