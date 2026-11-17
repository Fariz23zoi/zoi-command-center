# Suara ZOI di Windows (diperiksa 17 Nov 2026)

| Bagian | Yang dibutuhkan |
|---|---|
| Membacakan jawaban (bawaan) | Suara Bahasa Indonesia di perangkat yang membuka ZOI. Laptop: Settings › Time & Language › Speech › Add voices › Indonesian. HP Android: Settings › Text-to-speech › Speech Services by Google › Indonesia. |
| Mikrofon (Whisper) | Python **3.14** (paket `onnxruntime` belum tersedia untuk Python 3.15 di Windows), paket suara, dan model. |
| Suara Piper (opsional) | Program terpisah di port **5001** (5000 dipakai ZOI AI CLIPPER). Hanya pemakaian pribadi. |

## Mikrofon
```
py -3.14 --version
powershell -ExecutionPolicy Bypass -File deploy\windows\stop.ps1
Remove-Item -Recurse -Force backend\.venv
py -3.14 -m venv backend\.venv
powershell -ExecutionPolicy Bypass -File deploy\windows\install.ps1
backend\.venv\Scripts\pip install -r backend\requirements-voice.txt
backend\.venv\Scripts\python -c "from faster_whisper import download_model; download_model('tiny', output_dir=r'C:\ZOI\models\whisper-tiny')"
```
Isi `.env`: `ZOI_WHISPER_MODEL_DIR=C:\ZOI\models\whisper-tiny`, lalu jalankan ulang ZOI.
Mikrofon di HP butuh HTTPS (alamat Tailscale `https://…ts.net`), bukan alamat `http://`.

## Piper
```
py -3.14 -m venv C:\zoi-piper
C:\zoi-piper\Scripts\pip install "piper-tts[http]==1.8.0"
C:\zoi-piper\Scripts\python -m piper.download_voices --data-dir C:\ZOI\models\piper id_ID-news_tts-medium
powershell -ExecutionPolicy Bypass -File deploy\windows\voice.ps1 -VoiceDir C:\ZOI\models\piper
```
