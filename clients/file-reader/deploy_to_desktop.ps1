# Stop a running Desktop file-reader, then copy the latest build there.
# Run after build_windows.ps1 from this directory (or repo root).

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$src = Join-Path $here "dist\mindgraph-file-reader.exe"
$dest = Join-Path $env:USERPROFILE "Desktop\mindgraph-file-reader.exe"

if (-not (Test-Path $src)) {
    throw "Build output not found: $src — run .\build_windows.ps1 first"
}

foreach ($procName in @("mindgraph-file-reader", "mindgraph-file-reader-review")) {
    Get-Process -Name $procName -ErrorAction SilentlyContinue | Stop-Process -Force
}

Start-Sleep -Milliseconds 400
Copy-Item -Force $src $dest

$sizeMb = [math]::Round((Get-Item $dest).Length / 1MB, 1)
Write-Host "Deployed $dest ($sizeMb MB)"
