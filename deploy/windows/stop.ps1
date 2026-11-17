<#
.SYNOPSIS
  Hentikan ZOI - baik yang dijalankan di latar belakang (-Background) maupun di jendela PowerShell,
  dari folder mana pun (mis. versi lama yang masih berjalan).
#>
. (Join-Path $PSScriptRoot "common.ps1")

$stopped = $false
if (Test-Path $PidFile) {
    $procId = Get-Content $PidFile
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($proc -and $proc.Path -and ($proc.Path -like "*python*")) {
        Stop-Process -Id $procId -Force
        Write-Zoi "ZOI dihentikan (PID $procId)." "Green"
        $stopped = $true
    }
    Remove-Item $PidFile -ErrorAction SilentlyContinue
}

# ZOI yang dijalankan di jendela tidak punya zoi.pid: cari lewat port.
$port = Get-ZoiPort
$owner = Get-PortOwner $port
if ($owner) {
    if ($owner.Name -like "python*" -and "$($owner.CommandLine)" -match "-m app") {
        Stop-Process -Id $owner.ProcessId -Force
        Write-Zoi "ZOI di port $port dihentikan (PID $($owner.ProcessId), $($owner.ExecutablePath))." "Green"
        $stopped = $true
    } else {
        Write-Zoi "Port $port dipakai program lain ($($owner.Name)) - tidak dihentikan." "Yellow"
    }
}
if (-not $stopped) { Write-Zoi "Tidak ada ZOI yang berjalan." }
