# ADR 0015 — Online lewat laptop + Tailscale Serve

Tanggal: 16 November 2026 · Status: diterima

## Konteks
Hosting backend gratis tanpa kartu tidak tersedia (dicek 16 Nov 2026): Render minta kartu; SnapDeploy mewajibkan
paket berbayar untuk WebSocket; Back4App gratis hidup 60 menit per deploy; Zeabur gratis tanpa hosting; Railway $1/bulan
tidak cukup; Koyeb/Cloud Run/Cloudflare Containers/HF Docker Spaces berbayar atau minta kartu; Pages/Netlify/Vercel/
GitHub Pages hanya statis/fungsi singkat. Pengguna menyerahkan keputusan: "harus bisa online dan offline".

## Keputusan
ZOI berjalan di laptop (mode local). Akses jarak jauh lewat **Tailscale Serve** (Personal, gratis): hanya tailnet
pemilik, HTTPS otomatis. ZOI menerima alamat `ZOI_REMOTE_URL` (.ts.net, https) sebagai host & origin tepercaya, dan
permintaan lewat alamat itu **wajib** membawa header `Tailscale-User-Login` (Serve menghapus salinan palsu); bila
`ZOI_REMOTE_USER` diisi, login harus sama. Funnel (publik) tidak dipakai. Mode online (ADR 0012) tetap tersedia bila
kelak ada hosting yang memenuhi syarat.

## Konsekuensi
- Online hanya saat laptop menyala & tersambung; tidak ada biaya.
- Header Host yang dikirim Serve tidak didokumentasikan Tailscale; ZOI menerima keduanya (host .ts.net dengan
  identitas wajib, atau 127.0.0.1). Belum diuji dengan Tailscale sungguhan.
