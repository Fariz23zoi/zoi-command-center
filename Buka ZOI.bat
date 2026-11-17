@echo off
rem Klik dua kali untuk menjalankan ZOI dari folder ini. Jendela ini harus tetap terbuka selama ZOI dipakai.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy\windows\start.ps1" -OpenBrowser
pause
