<#
.SYNOPSIS
  Jalankan server suara Piper (program terpisah, GPL-3.0) untuk suara ZOI.
.DESCRIPTION
  Skrip ini TIDAK memasang dan TIDAK mengunduh apa pun. Siapkan dulu (lihat Settings > Suara):
    python -m venv C:\zoi-piper
    C:\zoi-piper\Scripts\pip install "piper-tts[http]==1.8.0"
    C:\zoi-piper\Scripts\python -m piper.download_voices --data-dir D:\zoi-models\piper id_ID-news_tts-medium
.PARAMETER PiperPython
  python.exe di venv Piper. Bawaan: C:\zoi-piper\Scripts\python.exe
.PARAMETER VoiceDir
  Folder berisi file suara (.onnx dan .onnx.json). Bawaan: D:\zoi-models\piper
.PARAMETER Voice
  Nama suara. Bawaan: id_ID-news_tts-medium
.PARAMETER Port
  Port server Piper. Harus sama dengan ZOI_PIPER_URL. Bawaan: 5000
#>
param(
    [string]$PiperPython = "C:\zoi-piper\Scripts\python.exe",
    [string]$VoiceDir = "D:\zoi-models\piper",
    [string]$Voice = "id_ID-news_tts-medium",
    [int]$Port = 5000
)
. (Join-Path $PSScriptRoot "common.ps1")

if (-not (Test-Path $PiperPython)) {
    Write-Zoi "Piper belum dipasang di $PiperPython. Lihat Settings > Suara untuk perintah pemasangan." "Red"; exit 1
}
$model = Join-Path $VoiceDir "$Voice.onnx"
if (-not (Test-Path $model) -or -not (Test-Path "$model.json")) {
    Write-Zoi "File suara tidak ditemukan: $model (dan $model.json). ZOI tidak mengunduh suara." "Red"; exit 1
}
Write-Zoi "Catatan lisensi: dataset suara $Voice tidak jelas - hanya untuk pemakaian pribadi, jangan untuk video yang dipublikasikan." "Yellow"
Write-Zoi "Server Piper di http://127.0.0.1:$Port (tekan Ctrl+C untuk berhenti)" "Green"
& $PiperPython -m piper.http_server --host 127.0.0.1 --port $Port --data-dir $VoiceDir -m $Voice
