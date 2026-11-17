<#
.SYNOPSIS
  Dijalankan otomatis oleh tombol "Update" di ZOI (Settings > Update). Jangan dijalankan manual kecuali diminta.
.DESCRIPTION
  Folder ini = versi baru (sudah diunduh & hash-nya dicocokkan oleh ZOI). Skrip ini:
  1. menghentikan ZOI lama, menyalin .env & data, memasang paket (upgrade.ps1 -Yes),
  2. menyalakan versi baru,
  3. bila gagal: menyalakan lagi versi lama. Folder lama tidak dihapus.
  Catatan proses ditulis ke update.log di folder ini.
#>
param([Parameter(Mandatory = $true)][string]$From)
. (Join-Path $PSScriptRoot "common.ps1")

$log = Join-Path $RepoRoot "update.log"
Start-Transcript -Path $log -Append | Out-Null
Write-Zoi "Memasang ZOI versi baru di $RepoRoot" "Green"
Write-Zoi "Versi lama tetap di $From (tidak dihapus)." "Yellow"
Start-Sleep -Seconds 2

$ok = $false
try {
    & (Join-Path $PSScriptRoot "upgrade.ps1") -From $From -Yes
    if (Test-Path $VenvPython) {
        & $VenvPython -c "import fastapi, sqlalchemy, httpx" 2>$null
        $ok = ($LASTEXITCODE -eq 0)
    }
} catch {
    Write-Zoi "Kesalahan: $_" "Red"
}

if ($ok) {
    Write-Zoi "Menyalakan versi baru..." "Green"
    Start-Process -FilePath (Join-Path $RepoRoot "Buka ZOI.bat") -WorkingDirectory $RepoRoot
} else {
    Write-Zoi "Update GAGAL - paket Python versi baru tidak lengkap. Menyalakan lagi versi lama." "Red"
    $oldStart = Join-Path $From "deploy\windows\start.ps1"
    Start-Process -FilePath "powershell" -WorkingDirectory $From `
        -ArgumentList "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$oldStart`"", "-OpenBrowser"
    Write-Zoi "Kirim isi file $log bila perlu bantuan." "Yellow"
}
Stop-Transcript | Out-Null
Read-Host "Tekan Enter untuk menutup jendela ini"
