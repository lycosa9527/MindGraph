# Build mindgraph-file-reader.exe with PyInstaller (Windows).
# Run from repo root or this directory in PowerShell.

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

python -m pip install --upgrade pyinstaller
python -m pip install -r requirements.txt

$ffmpegDir = Join-Path $here "tools"
$ffmpegExe = Join-Path $ffmpegDir "ffmpeg.exe"
$essentialsUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

function Ensure-EssentialsFfmpeg {
    param([string]$Destination)
    $maxFullBuildBytes = 150MB
    if ((Test-Path $Destination) -and ((Get-Item $Destination).Length -lt $maxFullBuildBytes)) {
        Write-Host "Using existing essentials ffmpeg at $Destination"
        return
    }
    if (Test-Path $Destination) {
        Write-Host "Replacing full ffmpeg build with essentials (smaller onefile bundle)..."
        Remove-Item $Destination -Force
    } else {
        Write-Host "Downloading ffmpeg essentials for onefile bundle..."
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $Destination) | Out-Null
    $zipPath = Join-Path $env:TEMP "ffmpeg-release-essentials.zip"
    $extractDir = Join-Path $env:TEMP "ffmpeg-essentials-extract"
    if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force }
    curl.exe -L --retry 3 --retry-delay 2 -o $zipPath $essentialsUrl
    Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force
    $source = Get-ChildItem -Path $extractDir -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
    if (-not $source) {
        throw "ffmpeg.exe not found in essentials archive"
    }
    Copy-Item $source.FullName -Destination $Destination -Force
    $sizeMb = [math]::Round((Get-Item $Destination).Length / 1MB, 1)
    Write-Host "Bundled ffmpeg essentials: $Destination ($sizeMb MB)"
}

Ensure-EssentialsFfmpeg -Destination $ffmpegExe

function Ensure-WxKeyDll {
    param([string]$Destination)
    if (Test-Path $Destination) {
        Write-Host "Using existing wx_key.dll at $Destination"
        return
    }
    $releaseUrl = "https://github.com/ycccccccy/wx_key/releases/download/v2.1.8/wx_key-windows-v2.1.8.zip"
    Write-Host "Downloading wx_key.dll for Weixin 4.1.10.31+ hook support..."
    New-Item -ItemType Directory -Force -Path (Split-Path $Destination) | Out-Null
    $zipPath = Join-Path $env:TEMP "wx_key-windows.zip"
    $extractDir = Join-Path $env:TEMP "wx_key-extract"
    if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force }
    curl.exe -L --retry 3 --retry-delay 2 -o $zipPath $releaseUrl
    Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force
    $source = Get-ChildItem -Path $extractDir -Recurse -Filter "wx_key.dll" | Select-Object -First 1
    if (-not $source) {
        Write-Warning "wx_key.dll not found in release archive — Weixin 4.1.10.31+ key hook will be unavailable"
        return
    }
    Copy-Item $source.FullName -Destination $Destination -Force
    $sizeMb = [math]::Round((Get-Item $Destination).Length / 1MB, 2)
    Write-Host "Bundled wx_key.dll: $Destination ($sizeMb MB)"
}

$wxKeyDll = Join-Path $here "tools\wx_key.dll"
Ensure-WxKeyDll -Destination $wxKeyDll

python -m pip install pillow
python (Join-Path $here "scripts\generate_icon.py")
if ($LASTEXITCODE -ne 0) {
    throw "Icon generation failed with exit code $LASTEXITCODE"
}

$playwrightDriver = python -c "import pathlib, playwright; print(pathlib.Path(playwright.__file__).resolve().parent / 'driver')"
if (-not (Test-Path $playwrightDriver)) {
    throw "Playwright driver not found at $playwrightDriver — run: python -m pip install playwright"
}

$env:PLAYWRIGHT_BROWSERS_PATH = "0"
Write-Host "Installing bundled Chromium into Playwright driver (PLAYWRIGHT_BROWSERS_PATH=0)..."
python -m playwright install chromium
if ($LASTEXITCODE -ne 0) {
    throw "playwright install chromium failed with exit code $LASTEXITCODE"
}

$localBrowsers = Join-Path $playwrightDriver "package\.local-browsers"
$chromeExe = Get-ChildItem -Path $localBrowsers -Recurse -Filter "chrome.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $chromeExe) {
    throw "Bundled Chromium not found under $localBrowsers — expected playwright install chromium with PLAYWRIGHT_BROWSERS_PATH=0"
}
$chromeMb = [math]::Round($chromeExe.Length / 1MB, 1)
Write-Host "Bundling Playwright driver + Chromium from $playwrightDriver ($($chromeExe.FullName), chrome.exe $chromeMb MB)"

pyinstaller --noconfirm mindgraph-file-reader.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$dist = Join-Path $here "dist\mindgraph-file-reader.exe"
if (-not (Test-Path $dist)) {
    throw "Build failed: $dist not found"
}

$distMb = [math]::Round((Get-Item $dist).Length / 1MB, 1)
Write-Host "Built onefile $dist ($distMb MB, ffmpeg + Playwright driver + bundled Chromium)"

$zipRoot = Join-Path $here "..\..\frontend\public\downloads"
New-Item -ItemType Directory -Force -Path $zipRoot | Out-Null
$zipPath = Join-Path $zipRoot "mindgraph-file-reader.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

$zipItems = @($dist, (Join-Path $here "README.md"))
Compress-Archive -Path $zipItems -DestinationPath $zipPath
Write-Host "Published $zipPath"
