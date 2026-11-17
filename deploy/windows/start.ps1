<#
.SYNOPSIS
  Jalankan ZOI. Mode local + port 80 -> buka http://127.0.0.1
.PARAMETER Background
  Jalankan tanpa jendela konsol (PID disimpan di zoi.pid).
.PARAMETER OpenBrowser
  Buka browser setelah ZOI siap.
#>
param([switch]$Background, [switch]$OpenBrowser)
. (Join-Path $PSScriptRoot "common.ps1")

if (-not (Test-Path $VenvPython)) { Write-Zoi "Belum dipasang. Jalankan dulu deploy\windows\install.ps1" "Red"; exit 1 }
if (Test-Path $PidFile) {
    $old = Get-Content $PidFile -ErrorAction SilentlyContinue
    if ($old -and (Get-Process -Id $old -ErrorAction SilentlyContinue)) {
        Write-Zoi "ZOI sudah berjalan (PID $old). Hentikan dulu dengan stop.ps1." "Yellow"
        exit 0
    }
    Remove-Item $PidFile -ErrorAction SilentlyContinue
}

$port = Get-ZoiPort
$owner = Get-PortOwner $port
if ($owner) {
    Write-Zoi "Port $port sudah dipakai: $($owner.ExecutablePath)" "Red"
    Write-Zoi "Kemungkinan ZOI (mungkin versi/folder lain) masih berjalan. Jalankan dulu: deploy\windows\stop.ps1" "Yellow"
    exit 1
}

Push-Location $Backend
try {
    & $VenvPython -m app.cli doctor
    if ($LASTEXITCODE -ne 0) { Write-Zoi "Pemeriksaan gagal - perbaiki baris FAIL di atas." "Red"; exit 1 }
    $url = (& $VenvPython -c "from app.config.modes import resolve_runtime; from app.config.settings import load_settings; print(resolve_runtime(load_settings()).base_url)").Trim()

    if ($Background) {
        $proc = Start-Process -FilePath $VenvPython -ArgumentList "-m", "app" -WorkingDirectory $Backend `
            -WindowStyle Hidden -PassThru
        Set-Content -Path $PidFile -Value $proc.Id -Encoding ascii
        Write-Zoi "ZOI berjalan di latar belakang (PID $($proc.Id)): $url" "Green"
        if ($OpenBrowser) { Start-Sleep -Seconds 3; Start-Process $url }
    } else {
        if ($OpenBrowser) { Start-Job -ScriptBlock { param($u) Start-Sleep 3; Start-Process $u } -ArgumentList $url | Out-Null }
        Write-Zoi "Membuka $url  (tekan Ctrl+C untuk berhenti)" "Green"
        & $VenvPython -m app
    }
} finally { Pop-Location }
