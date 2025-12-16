# Offline Browser Installation Guide

This guide explains how to use the packaged Chromium browser for fast offline installation on new servers.

## Problem

Downloading Chromium via Playwright on new server deployments can take 5-10 minutes and requires internet access. This slows down deployment significantly.

## Solution

Package Chromium into a zip file once, then extract it on new servers for instant installation.

## Workflow

### Step 1: Package Chromium (One-time, on development machine)

```bash
# Install Playwright and Chromium first
python -m playwright install chromium

# Package Chromium into zip
python scripts/package_browsers.py
```

This creates `browsers/chromium.zip` (~150MB compressed).

### Step 2: Distribute the Zip File

**Option A: Upload to GitHub Releases (Recommended)**
- Create a GitHub release
- Upload `browsers/chromium.zip` as an asset
- Users can download it from releases

**Option B: Upload to Server Directly**
- Use `scp`, `rsync`, or FTP to upload `browsers/chromium.zip` to the server
- Place it in the `browsers/` directory

**Option C: Include in Deployment Package**
- Package the zip with your deployment files
- Extract during deployment

### Step 3: Deploy on New Server

```bash
# Upload chromium.zip to browsers/ directory first, then:
python scripts/setup.py
```

Setup will automatically:
1. Detect `browsers/chromium.zip`
2. Extract it to `browsers/chromium/`
3. Skip Playwright browser download (saves 5-10 minutes!)

## How It Works

The `setup.py` script checks for `browsers/chromium.zip` first:

1. **If zip exists**: Extract it (fast, ~30 seconds)
2. **If zip doesn't exist**: Download via Playwright (slow, ~5-10 minutes)
3. **If already extracted**: Skip installation

## Platform Support

The zip file is platform-specific. You need separate zips for:
- Windows (`chromium-win.zip`)
- Linux (`chromium-linux.zip`)
- macOS (`chromium-mac.zip`)

To package for different platforms:

```bash
# On Windows machine
python scripts/package_browsers.py
# Creates: browsers/chromium-win.zip

# On Linux machine
python scripts/package_browsers.py
# Creates: browsers/chromium-linux.zip

# On macOS machine
python scripts/package_browsers.py
# Creates: browsers/chromium-mac.zip
```

## File Structure

```
MindGraph/
├── browsers/
│   ├── chromium.zip          # Packaged browser (upload this)
│   └── chromium/             # Extracted browser (auto-created)
│       └── chrome.exe         # Browser executable
└── scripts/
    ├── package_browsers.py   # Package script
    └── setup.py              # Auto-extracts zip if found
```

## Benefits

✅ **Fast Deployment**: Extract zip in ~30 seconds vs 5-10 minutes download  
✅ **Offline Installation**: No internet required on server  
✅ **Reliable**: No network timeouts or download failures  
✅ **Version Control**: Use same browser version across deployments  
✅ **Git-Friendly**: Zip is ignored by git (too large), upload to releases instead

## Troubleshooting

### Zip extraction fails

```bash
# Check zip file integrity
python -c "import zipfile; zipfile.ZipFile('browsers/chromium.zip').testzip()"

# Manually extract
unzip browsers/chromium.zip -d browsers/chromium/
```

### Wrong platform zip

Make sure you're using the correct zip for your platform:
- Windows servers need `chromium-win.zip`
- Linux servers need `chromium-linux.zip`
- macOS servers need `chromium-mac.zip`

### Setup still downloads Playwright

If setup.py still tries to download Playwright:
1. Check that `browsers/chromium.zip` exists
2. Check file permissions (should be readable)
3. Check disk space (need ~200MB free)

## Advanced: Multi-Platform Zip

To support multiple platforms in one zip:

```bash
# Package all platforms
python scripts/package_browsers.py --platform windows
python scripts/package_browsers.py --platform linux
python scripts/package_browsers.py --platform macos

# Creates:
# browsers/chromium-windows.zip
# browsers/chromium-linux.zip
# browsers/chromium-mac.zip
```

Then upload the appropriate zip for your server platform.

