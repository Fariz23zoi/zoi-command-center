<#
.SYNOPSIS
  (Opsional) Jalankan ZOI otomatis saat login, memakai Task Scheduler bawaan Windows.
.PARAMETER Remove
  Hapus jadwal autostart.
#>
param([switch]$Remove)
. (Join-Path $PSScriptRoot "common.ps1")

$taskName = "ZOI Command Center"
if ($Remove) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Zoi "Autostart dihapus." "Green"
    exit 0
}
$script = Join-Path $PSScriptRoot "start.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`" -Background"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Description "Menjalankan ZOI saat login (dibuat oleh deploy\windows\autostart.ps1)" -Force | Out-Null
Write-Zoi "Autostart aktif: ZOI berjalan setiap kali $env:USERNAME login. Hapus dengan: autostart.ps1 -Remove" "Green"
