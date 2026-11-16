<#
.SYNOPSIS
  Pasang ZOI di local server Windows (membuat venv dan memasang paket Python).
.DESCRIPTION
  - TIDAK mengunduh model AI. TIDAK memasang Ollama. TIDAK mengubah ZOI AI CLIPPER / Blueprint Studio.
  - Memeriksa Python 3.12+ dan ruang disk SEBELUM memasang apa pun.
  - Meminta persetujuan sebelum mengunduh paket Python (+/- 80 MB dari PyPI).
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File deploy\windows\install.ps1
#>
param(
    [switch]$Yes,
    [double]$ReserveGB = 5
)
. (Join-Path $PSScriptRoot "common.ps1")

Write-Zoi "Folder ZOI: $RepoRoot"

# 1) Python
$py = Find-Python312
if (-not $py) {
    Write-Zoi "Python 3.12 atau lebih baru tidak ditemukan." "Red"
    Write-Zoi "Pasang dari https://www.python.org/downloads/windows/ (centang 'Add python.exe to PATH'), lalu jalankan ulang." "Yellow"
    exit 1
}
Write-Zoi ("Python ditemukan: " + $py.Version) "Green"

# 2) Frontend hasil build (paket rilis sudah berisi folder ini)
$dist = Join-Path $RepoRoot "frontend\apps\web\dist\index.html"
if (-not (Test-Path $dist)) {
    Write-Zoi "Frontend hasil build tidak ditemukan: $dist" "Red"
    Write-Zoi "Gunakan paket rilis ZOI (zip) yang sudah berisi frontend. Node.js tidak diperlukan di local server." "Yellow"
    exit 1
}

# 3) Ruang disk: perkiraan kebutuhan + cadangan untuk Windows
$needGB = 0.3
$freeGB = Get-FreeGB $RepoRoot
Write-Zoi "Ruang kosong: $freeGB GB. Kebutuhan ZOI: +/- $needGB GB. Cadangan yang dijaga: $ReserveGB GB."
if (($freeGB - $needGB) -lt $ReserveGB) {
    Write-Zoi "Ruang disk tidak cukup: setelah instalasi tersisa kurang dari $ReserveGB GB. Instalasi dibatalkan." "Red"
    exit 1
}

# 4) Persetujuan unduhan paket
if (-not $Yes) {
    $answer = Read-Host "[ZOI] Buat venv dan unduh paket Python (+/- 80 MB dari pypi.org)? [y/N]"
    if ($answer -notin @("y", "Y", "ya", "yes")) { Write-Zoi "Dibatalkan."; exit 1 }
}

# 5) venv + paket runtime saja (tanpa paket pengembangan)
if (-not (Test-Path $VenvPython)) {
    & $py.Exe @($py.Args) -m venv (Join-Path $Backend ".venv")
    if ($LASTEXITCODE -ne 0) { Write-Zoi "Gagal membuat venv." "Red"; exit 1 }
}
& $VenvPython -m pip install --disable-pip-version-check -r (Join-Path $Backend "requirements.txt")
if ($LASTEXITCODE -ne 0) { Write-Zoi "Gagal memasang paket Python." "Red"; exit 1 }

# 6) File konfigurasi
$envFile = Join-Path $RepoRoot ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $RepoRoot ".env.local.example") $envFile
    Write-Zoi "File .env dibuat dari .env.local.example. Periksa isinya (ZOI_OLLAMA_MODEL, path CLIPPER/Blueprint)." "Yellow"
}

# 7) Pemeriksaan akhir
Push-Location $Backend
try { & $VenvPython -m app.cli doctor } finally { Pop-Location }
Write-Zoi "Instalasi selesai. Jalankan: deploy\windows\start.ps1" "Green"
