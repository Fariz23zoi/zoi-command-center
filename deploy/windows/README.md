# Deploy ZOI di local server Windows

> Status: skrip ini ditulis untuk Windows PowerShell 5.1 / PowerShell 7, **belum dijalankan di Windows sungguhan**
> (lingkungan pengembangan tidak memiliki PowerShell). Uji nyata dilakukan saat migrasi — lihat
> `docs/MIGRATION_TO_LOCAL_SERVER.md`.

| Skrip | Fungsi |
|---|---|
| `install.ps1` | Cek Python 3.12+, cek ruang disk (menjaga cadangan 5 GB), minta persetujuan, buat `backend\.venv`, pasang paket runtime, buat `.env` dari `.env.local.example`, jalankan `doctor` |
| `start.ps1` | Jalankan `doctor`, lalu ZOI. `-Background` tanpa jendela, `-OpenBrowser` membuka browser |
| `stop.ps1` | Hentikan ZOI yang berjalan di latar belakang |
| `autostart.ps1` | Opsional: jalankan otomatis saat login (Task Scheduler bawaan). `-Remove` untuk menghapus |

Jalankan dari folder ZOI:

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\install.ps1
powershell -ExecutionPolicy Bypass -File deploy\windows\start.ps1 -OpenBrowser
```

`-ExecutionPolicy Bypass` hanya berlaku untuk perintah itu; kebijakan sistem tidak diubah.

Yang **tidak** dilakukan skrip ini: memasang Ollama, mengunduh model AI, mengubah ZOI AI CLIPPER / Blueprint
Studio, membuka akses dari jaringan lain, atau mematikan program lain yang memakai port 80.
