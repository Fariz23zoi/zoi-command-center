<#
.SYNOPSIS
  Hentikan ZOI yang dijalankan dengan start.ps1 -Background.
#>
. (Join-Path $PSScriptRoot "common.ps1")

if (-not (Test-Path $PidFile)) { Write-Zoi "Tidak ada ZOI yang berjalan di latar belakang (zoi.pid tidak ada)."; exit 0 }
$procId = Get-Content $PidFile
$proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
if ($proc -and $proc.Path -and ($proc.Path -like "*python*")) {
    Stop-Process -Id $procId
    Write-Zoi "ZOI dihentikan (PID $procId)." "Green"
} else {
    Write-Zoi "Proses $procId sudah tidak berjalan." "Yellow"
}
Remove-Item $PidFile -ErrorAction SilentlyContinue
