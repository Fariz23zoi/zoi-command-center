# ZOI - fungsi bersama untuk skrip Windows. Hanya karakter ASCII (aman untuk Windows PowerShell 5.1).
$ErrorActionPreference = "Stop"

$Script:RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Script:Backend = Join-Path $RepoRoot "backend"
$Script:VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
$Script:PidFile = Join-Path $RepoRoot "zoi.pid"

function Write-Zoi([string]$Message, [string]$Color = "Gray") {
    Write-Host "[ZOI] $Message" -ForegroundColor $Color
}

function Find-Python312 {
    # Mengembalikan perintah Python 3.12+ yang tersedia, atau $null.
    foreach ($candidate in @("py -3.12", "py -3", "python")) {
        $parts = $candidate.Split(" ")
        $exeName = $parts[0]
        $pyArgs = @()
        if ($parts.Length -gt 1) { $pyArgs = @($parts[1..($parts.Length - 1)]) }
        if (-not (Get-Command $exeName -ErrorAction SilentlyContinue)) { continue }
        try {
            $version = & $exeName @pyArgs -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        } catch { continue }
        if ($version -and ([version]"$version" -ge [version]"3.12")) {
            return @{ Exe = $exeName; Args = $pyArgs; Version = "$version" }
        }
    }
    return $null
}

function Get-FreeGB([string]$Path) {
    $root = [System.IO.Path]::GetPathRoot((Resolve-Path $Path).Path)
    $drive = Get-PSDrive -Name $root.Substring(0, 1) -PSProvider FileSystem
    return [math]::Round($drive.Free / 1GB, 2)
}
