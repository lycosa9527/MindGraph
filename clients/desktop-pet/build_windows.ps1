# Build a windowed onedir pet. Run from Windows, not WSL.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --windowed --onedir --name "MindGraph Pet" `
  --add-data "VERSION;." `
  --add-data "assets;assets" `
  --collect-all keyring `
  mindgraph_pet/__main__.py
$runtime = Join-Path (Split-Path (Get-Command python).Source) "Library\bin"
$internal = Join-Path $PSScriptRoot "dist\MindGraph Pet\_internal"
foreach ($name in @(
    "libssl-3-x64.dll", "libcrypto-3-x64.dll", "ffi.dll",
    "libexpat.dll", "liblzma.dll", "libbz2.dll", "libmpdec-4.dll"
)) {
  $source = Join-Path $runtime $name
  if (Test-Path $source) {
    Copy-Item $source $internal -Force
  }
}
Write-Host "dist\MindGraph Pet\MindGraph Pet.exe"
