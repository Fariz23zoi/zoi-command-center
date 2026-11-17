@echo off
rem Menghentikan ZOI (dari folder mana pun yang sedang berjalan).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy\windows\stop.ps1"
pause
