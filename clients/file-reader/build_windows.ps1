# Build mindgraph-file-reader.exe with PyInstaller (Windows).
# Run from repo root or this directory in PowerShell.

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

python -m pip install --upgrade pyinstaller
pyinstaller --noconfirm --onefile --windowed --name mindgraph-file-reader `
  --add-data "assets/icon.png;assets" `
  file_reader/__main__.py

$dist = Join-Path $here "dist\mindgraph-file-reader.exe"
if (-not (Test-Path $dist)) {
    throw "Build failed: $dist not found"
}

$zipRoot = Join-Path $here "..\..\frontend\public\downloads"
New-Item -ItemType Directory -Force -Path $zipRoot | Out-Null
$zipPath = Join-Path $zipRoot "mindgraph-file-reader.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path $dist, (Join-Path $here "README.md") -DestinationPath $zipPath
Write-Host "Built $dist and $zipPath"
