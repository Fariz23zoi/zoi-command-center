# Membuka ZOI dari HP (online) — laptop sebagai server, lewat Tailscale

**Offline**: buka ZOI langsung di laptop (`http://127.0.0.1`).
**Online**: buka dari HP di mana saja lewat Tailscale. Syarat: **laptop menyala dan tersambung internet**.

Gratis: Tailscale paket Personal $0 "Free forever", hanya untuk pemakaian non-komersial Tailscale.
ZOI hanya terjangkau perangkat di tailnet-mu (Tailscale **Serve**, bukan Funnel) — tidak terbuka ke internet umum.

## 1. Pasang ZOI di laptop
Ikuti `MIGRATION_TO_LOCAL_SERVER.md` sampai ZOI terbuka di `http://127.0.0.1`.

## 2. Pasang Tailscale (laptop & HP)
1. Laptop: unduh dari **tailscale.com/download** (Windows), pasang, lalu **Log in** — pakai akun Google atau GitHub-mu.
2. HP: pasang aplikasi **Tailscale** dari Play Store, **Log in dengan akun yang sama**, lalu aktifkan (tombol Connect).

## 3. Bagikan ZOI ke HP
Di laptop, buka **PowerShell** dan jalankan (port 80; ganti bila `ZOI_PORT` lain):

```powershell
tailscale serve --bg 80
tailscale serve status
```

- Bila diminta mengaktifkan HTTPS, buka tautan yang muncul dan setujui.
- `serve status` menampilkan alamat seperti `https://laptop-zoi.tail1234.ts.net`. Dengan `--bg`, pengaturan ini tetap
  aktif setelah laptop dinyalakan ulang.

## 4. Beri tahu ZOI alamatnya
Di file `.env` ZOI:

```ini
ZOI_REMOTE_URL=https://laptop-zoi.tail1234.ts.net
ZOI_REMOTE_USER=email-akun-tailscale-mu@gmail.com
```

Hentikan lalu jalankan ulang ZOI (`stop.ps1`, `start.ps1`). Buka alamat tadi di **browser HP** (Tailscale aktif).

## 5. Agar selalu bisa dibuka
- Jalankan `deploy\windows\autostart.ps1` agar ZOI menyala saat login Windows.
- **Settings Windows › System › Power**: set *Sleep* "Never" saat dicolok listrik (laptop yang tidur = ZOI tidak bisa dibuka).

## Keamanan
- Hanya perangkat yang masuk ke tailnet-mu yang bisa menjangkau alamat itu.
- Permintaan lewat alamat `.ts.net` wajib membawa identitas Tailscale; dengan `ZOI_REMOTE_USER`, hanya akun itu yang diterima.
- Jangan pakai `tailscale funnel` untuk ZOI — Funnel membuka ke internet publik.

## Masalah
| Gejala | Langkah |
|---|---|
| Alamat .ts.net tidak terbuka di HP | Aplikasi Tailscale di HP aktif? Laptop menyala & Tailscale-nya terhubung? |
| "Akses lewat Tailscale butuh identitas" | Buka lewat Tailscale **Serve** (bukan Funnel), dari perangkat yang login ke tailnet. |
| "Akun Tailscale ini tidak diizinkan" | `ZOI_REMOTE_USER` beda dengan akun Tailscale di HP. |
| Host tidak diizinkan (400) | `ZOI_REMOTE_URL` belum diisi / salah ketik, atau ZOI belum dijalankan ulang. |
