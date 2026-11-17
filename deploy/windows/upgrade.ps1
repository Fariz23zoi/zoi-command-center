<#
.SYNOPSIS
  Pindahkan ZOI dari folder versi lama ke folder ini (versi baru), lalu buat pintasan di Desktop.
.DESCRIPTION
  - Menghentikan ZOI yang sedang berjalan (folder mana pun).
  - Menyalin .env dan folder data dari folder lama (tidak menimpa .env yang sudah ada di folder ini).
  - Memasang paket Python (install.ps1) bila backend\.venv belum ada.
  - Membuat pintasan "Buka ZOI", "Matikan ZOI", "Matikan Semua" di Desktop yang menunjuk ke folder INI.
  API key AI cloud dan token YouTube tersimpan di Windows Credential Manager - tidak perlu dimasukkan ulang.
.PARAMETER From
  Folder ZOI lama, mis. C:\ZOI\zoi-command-center-1.2.0
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File deploy\windows\upgrade.ps1 -From C:\ZOI\zoi-command-center-1.2.0
#>
param([Parameter(Mandatory = $true)][string]$From, [switch]$Yes)
. (Join-Path $PSScriptRoot "common.ps1")

$old = (Resolve-Path $From -ErrorAction SilentlyContinue).Path
if (-not $old -or -not (Test-Path (Join-Path $old "backend"))) { Write-Zoi "Folder ZOI lama tidak ditemukan: $From" "Red"; exit 1 }
if ($old -eq $RepoRoot) { Write-Zoi "Folder lama sama dengan folder ini." "Red"; exit 1 }

& (Join-Path $PSScriptRoot "stop.ps1")
& (Join-Path $old "deploy\windows\stop.ps1") 2>$null

$envOld = Join-Path $old ".env"
$envNew = Join-Path $RepoRoot ".env"
if ((Test-Path $envOld) -and -not (Test-Path $envNew)) { Copy-Item $envOld $envNew; Write-Zoi ".env disalin." "Green" }
elseif (Test-Path $envNew) { Write-Zoi ".env sudah ada di folder ini - tidak ditimpa." "Yellow" }

$dataOld = Join-Path $old "data"
if (Test-Path $dataOld) {
    robocopy $dataOld (Join-Path $RepoRoot "data") /E /NFL /NDL /NJH /NJS | Out-Null
    Write-Zoi "Folder data disalin." "Green"
}

if (-not (Test-Path $VenvPython)) { & (Join-Path $PSScriptRoot "install.ps1") -Yes:$Yes }

# Paket suara ikut dipasang bila versi lama memakainya.
$oldPy = Join-Path $old "backend\.venv\Scripts\python.exe"
if ((Test-Path $oldPy) -and (Test-Path $VenvPython)) {
    & $oldPy -c "import faster_whisper" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Zoi "Memasang paket suara (dipakai di versi lama)..."
        & $VenvPython -m pip install -q -r (Join-Path $Backend "requirements-voice.txt")
    }
}

$desktop = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell
foreach ($name in @("Buka ZOI", "Matikan ZOI", "Matikan Semua")) {
    $link = $shell.CreateShortcut((Join-Path $desktop "$name.lnk"))
    $link.TargetPath = Join-Path $RepoRoot "$name.bat"
    $link.WorkingDirectory = $RepoRoot
    $link.Save()
}
Write-Zoi "Pintasan Desktop dibuat dan menunjuk ke $RepoRoot." "Green"
Write-Zoi "File .bat lama di Desktop (bila ada) boleh dihapus. Jalankan ZOI dengan 'Buka ZOI'." "Yellow"
