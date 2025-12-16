# Multi-Platform Chromium Zip Creation Guide

This guide explains how to create a single `chromium.zip` file that contains Chromium browsers for Windows, Linux, and macOS.

## Current Status

✅ **Windows platform**: Already packaged in `browsers/chromium.zip`

⏳ **Linux platform**: Needs to be added  
⏳ **macOS platform**: Needs to be added

## How to Add Platforms

The `package_browsers.py` script can be run on each platform to incrementally add platforms to the same zip file.

### Step 1: Windows Platform (Already Done)

```bash
# On Windows machine
python scripts/package_browsers.py
```

✅ Creates/updates `browsers/chromium.zip` with `windows/` folder

### Step 2: Linux Platform

```bash
# On Linux machine
# 1. Clone or copy the repository
git clone <repo-url>
cd MindGraph

# 2. Install Playwright and Chromium
pip install playwright
python -m playwright install chromium

# 3. Copy the existing chromium.zip from Windows (or get it from team)
# Place it in browsers/ directory

# 4. Run packaging script (will add linux/ folder to existing zip)
python scripts/package_browsers.py
```

✅ Adds `linux/` folder to `browsers/chromium.zip`

### Step 3: macOS Platform

```bash
# On macOS machine
# 1. Clone or copy the repository
git clone <repo-url>
cd MindGraph

# 2. Install Playwright and Chromium
pip install playwright
python -m playwright install chromium

# 3. Copy the existing chromium.zip (with windows/ and linux/)
# Place it in browsers/ directory

# 4. Run packaging script (will add mac/ folder to existing zip)
python scripts/package_browsers.py
```

✅ Adds `mac/` folder to `browsers/chromium.zip`

## Final Result

After all three platforms are added:
- **File**: `browsers/chromium.zip`
- **Size**: ~450-500 MB (all three platforms)
- **Structure**:
  ```
  chromium.zip
  ├── windows/
  │   └── chrome.exe
  ├── linux/
  │   └── chrome
  └── mac/
      └── Chromium.app
  ```

## Distribution

Once complete, distribute the single `chromium.zip` file:
- Upload to shared drive/cloud storage
- Send via file transfer
- Include in deployment package

## Usage on Servers

On any server (Windows/Linux/macOS):
1. Upload `chromium.zip` to `browsers/` directory
2. Run `python scripts/setup.py`
3. Setup automatically extracts only the platform-specific folder

## Verification

Check what platforms are in the zip:
```bash
python -c "import zipfile; z = zipfile.ZipFile('browsers/chromium.zip'); platforms = set([f.split('/')[0] for f in z.namelist() if '/' in f and f.split('/')[0] in ['windows', 'linux', 'mac']]); print('Platforms:', sorted(platforms))"
```

## Troubleshooting

### Zip file is too large
- Each platform adds ~150MB
- Total size ~450-500MB is normal
- Consider compressing further or splitting if needed

### Platform not found in zip
- Make sure you copied the zip file before running the script
- Check that the script ran successfully
- Verify platform folder exists in zip

### Wrong platform extracted
- Setup.py automatically detects platform
- Make sure correct platform folder exists in zip
- Check platform detection: `python -c "import platform; print(platform.system())"`

