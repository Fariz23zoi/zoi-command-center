@echo off
rem Menghentikan ZOI, lalu ZOI AI CLIPPER (port 5000) dan server suara Piper (port 5001) bila menyala.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy\windows\stop.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "foreach ($p in 5000,5001) { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $x = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $_.OwningProcess); if ($x.Name -like 'python*') { Stop-Process -Id $_.OwningProcess -Force; Write-Host ('Port ' + $p + ' dihentikan: ' + $x.ExecutablePath) } else { Write-Host ('Port ' + $p + ' dipakai ' + $x.Name + ' - dibiarkan') } } }"
echo Selesai.
pause
