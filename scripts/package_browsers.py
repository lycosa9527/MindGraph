#!/usr/bin/env python3
"""
Package Playwright Browsers for Offline Distribution

This script packages Playwright's installed Chromium browser into a zip file
for easy distribution and offline installation. Supports multi-platform packaging.

Usage:
    python scripts/package_browsers.py

This will create/update browsers/chromium.zip containing Chromium for the current platform.
Run on Windows, Linux, and macOS to add all platforms to the same zip.

On new server deployments, users can:
    1. Upload browsers/chromium.zip to the server
    2. Run: python scripts/setup.py
    3. Setup will automatically extract the correct platform from the zip

The zip file can be uploaded to GitHub releases or distributed separately.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import os
import sys
import platform
import zipfile
import tempfile
import urllib.request
from pathlib import Path

def get_project_root():
    """Get the project root directory"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(script_dir) == "scripts":
        return os.path.dirname(script_dir)
    return script_dir

def download_playwright_browser_for_platform(target_platform):
    """
    Download Playwright Chromium for a specific platform directly from Playwright's CDN.

    Args:
        target_platform: 'windows', 'linux', or 'mac'

    Returns:
        Path to downloaded Chromium directory, or None if failed
    """
    print(f"[INFO] Downloading Chromium for {target_platform} platform...")
    print("    This may take 5-10 minutes (~150MB)...")

    try:
        # Get Chromium revision from current installation
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # Get browser revision
            browser_path = p.chromium.executable_path
            if browser_path:
                # Extract revision from path (e.g., chromium-1194)
                import re
                match = re.search(r'chromium-(\d+)', browser_path)
                if match:
                    revision = match.group(1)
                else:
                    # Try to get from Playwright's browser info
                    revision = "1194"  # Default to current revision
            else:
                revision = "1194"

        # Map platform names to Playwright CDN platform names
        platform_map = {
            "windows": "win64",
            "linux": "linux",
            "mac": "mac"
        }

        cdn_platform = platform_map.get(target_platform)
        if not cdn_platform:
            print(f"[ERROR] Unknown platform: {target_platform}")
            return None

        # Playwright CDN URL format
        zip_url = f"https://playwright.azureedge.net/builds/chromium/{revision}/chromium-{cdn_platform}.zip"

        print(f"[INFO] Downloading from: {zip_url}")

        # Create temp directory for download
        temp_dir = Path(tempfile.gettempdir()) / f"playwright-chromium-{target_platform}"
        temp_dir.mkdir(exist_ok=True)
        zip_file = temp_dir / f"chromium-{target_platform}.zip"

        # Download zip file
        def show_progress(block_num, block_size, total_size):
            downloaded = block_num * block_size
            percent = min(downloaded * 100 / total_size, 100) if total_size > 0 else 0
            print(f"\r    Downloading: {percent:.1f}% ({downloaded/(1024*1024):.1f}MB / {total_size/(1024*1024):.1f}MB)", end='', flush=True)

        urllib.request.urlretrieve(zip_url, zip_file, show_progress)
        print()  # New line after progress

        # Extract zip to temp directory
        extract_dir = temp_dir / "extracted"
        extract_dir.mkdir(exist_ok=True)

        print("[INFO] Extracting zip file...")
        with zipfile.ZipFile(zip_file, 'r') as zipf:
            zipf.extractall(extract_dir)

        # Find Chromium directory
        # Playwright extracts to chrome-{platform}/ or similar
        chromium_dirs = list(extract_dir.glob("chrome-*"))
        if chromium_dirs:
            chromium_dir = chromium_dirs[0]
        else:
            # Try other patterns
            chromium_dirs = list(extract_dir.glob("*"))
            if chromium_dirs:
                chromium_dir = chromium_dirs[0]
            else:
                print("[ERROR] Could not find Chromium directory in extracted files")
                return None

        print(f"[SUCCESS] Downloaded Chromium for {target_platform}")
        return chromium_dir

    except Exception as e:
        print(f"[WARNING] Failed to download Chromium for {target_platform}: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_playwright_browser_path(target_platform=None):
    """
    Get the path to Playwright's installed Chromium browser.
    If target_platform is specified and different from current, downloads it.

    Args:
        target_platform: 'windows', 'linux', 'mac', or None for current platform

    Returns:
        Path to Chromium executable, or None if not found
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser_path = p.chromium.executable_path
            if browser_path and os.path.exists(browser_path):
                # Check if this is the platform we want
                current_platform = get_platform_name()
                if target_platform and target_platform != current_platform:
                    # Need to download for different platform
                    chromium_dir = download_playwright_browser_for_platform(target_platform)
                    if chromium_dir and chromium_dir.exists():
                        # Return the directory, not executable (we'll package the whole dir)
                        return str(chromium_dir)
                    return None

                return browser_path
    except Exception as e:
        print(f"[ERROR] Could not get Playwright browser path: {e}")
        if not target_platform:
            print("[INFO] Please install Playwright first:")
            print("    python -m playwright install chromium")
        return None

    return None

def get_platform_name():
    """Get platform name for zip file naming"""
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "darwin":
        return "mac"
    elif system == "linux":
        return "linux"
    else:
        return system

def package_platform_chromium(zip_path, platform_name, chromium_source_dir):
    """Package a single platform's Chromium into the zip file"""
    # Check if zip already exists and what platforms it contains
    existing_platforms = []
    if zip_path.exists():
        with zipfile.ZipFile(zip_path, 'r') as existing_zip:
            for name in existing_zip.namelist():
                if name.startswith('windows/') or name.startswith('linux/') or name.startswith('mac/'):
                    platform_in_zip = name.split('/')[0]
                    if platform_in_zip not in existing_platforms:
                        existing_platforms.append(platform_in_zip)

        if existing_platforms:
            print(f"[INFO] Zip already contains: {', '.join(existing_platforms)}")
            if platform_name in existing_platforms:
                print(f"[INFO] {platform_name} platform already exists, will be replaced")

    print(f"[INFO] Packaging {platform_name} Chromium into zip...")
    print(f"    Source: {chromium_source_dir}")
    print("    This may take a few minutes (~150MB per platform)...")

    total_files = sum(1 for _ in chromium_source_dir.rglob('*') if _.is_file())
    processed = 0

    # Handle existing zip: remove old platform folder if updating
    if zip_path.exists() and platform_name in existing_platforms:
        print(f"[INFO] Removing existing {platform_name} platform from zip...")
        temp_zip = zip_path.with_suffix('.zip.tmp')
        with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as new_zip:
            with zipfile.ZipFile(zip_path, 'r') as old_zip:
                for item in old_zip.infolist():
                    if not item.filename.startswith(f'{platform_name}/'):
                        new_zip.writestr(item, old_zip.read(item.filename))
        zip_path.unlink()
        temp_zip.rename(zip_path)
        mode = 'a'
    else:
        mode = 'a' if zip_path.exists() else 'w'

    # Add/update platform folder in zip
    with zipfile.ZipFile(zip_path, mode, zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
        for root, dirs, files in os.walk(chromium_source_dir):
            for file in files:
                file_path = Path(root) / file
                relative_path = file_path.relative_to(chromium_source_dir)
                arcname = f"{platform_name}/{relative_path}"
                zipf.write(file_path, arcname)
                processed += 1
                if processed % 100 == 0:
                    print(f"    Progress: {processed}/{total_files} files...", end='\r')

    print(f"\n[SUCCESS] {platform_name} platform added to zip!")

def package_chromium():
    """Package Chromium browser into a multi-platform zip file"""
    project_root = get_project_root()
    browsers_dir = Path(project_root) / "browsers"
    browsers_dir.mkdir(exist_ok=True)

    # Single zip file for all platforms
    zip_path = browsers_dir / "chromium.zip"
    current_platform = get_platform_name()

    print("=" * 60)
    print("MindGraph Multi-Platform Browser Packager")
    print("=" * 60)
    print(f"Project root: {project_root}")
    print(f"Zip file: {zip_path}")
    print()

    # Platforms to package
    platforms_to_package = ['windows', 'linux', 'mac']

    print("[INFO] This will download and package Chromium for all platforms:")
    print("    - Windows")
    print("    - Linux")
    print("    - macOS")
    print()
    print("[INFO] This may take 15-30 minutes and download ~450MB...")
    print()

    for platform_name in platforms_to_package:
        print(f"\n{'='*60}")
        print(f"Processing {platform_name} platform...")
        print(f"{'='*60}")

        # Get Chromium for this platform
        if platform_name == current_platform:
            # Use current platform's installed Chromium
            playwright_chromium_path = get_playwright_browser_path()
            if not playwright_chromium_path:
                print(f"[ERROR] Chromium not found for {platform_name}")
                print("[INFO] Please install Chromium first:")
                print("    python -m playwright install chromium")
                continue
            # Find the Chromium directory (parent of executable)
            chromium_source_dir = Path(os.path.dirname(playwright_chromium_path))
        else:
            # Download for other platform (returns directory directly)
            print(f"[INFO] Downloading Chromium for {platform_name}...")
            chromium_source_dir = download_playwright_browser_for_platform(platform_name)
            if not chromium_source_dir:
                print(f"[WARNING] Could not download Chromium for {platform_name}, skipping...")
                continue
            chromium_source_dir = Path(chromium_source_dir)

        # On macOS, Chromium.app is a bundle
        if platform_name == "mac" and str(chromium_source_dir).endswith(".app"):
            chromium_source_dir = chromium_source_dir.parent

        if not chromium_source_dir.exists():
            print(f"[ERROR] Chromium directory not found: {chromium_source_dir}")
            continue

        # Package this platform
        package_platform_chromium(zip_path, platform_name, chromium_source_dir)

    # Check if zip already exists and what platforms it contains
    existing_platforms = []
    if zip_path.exists():
        print(f"[INFO] Existing zip file found, updating with {platform_name} platform...")
        with zipfile.ZipFile(zip_path, 'r') as existing_zip:
            # Check what platforms are already in the zip
            for name in existing_zip.namelist():
                if name.startswith('windows/') or name.startswith('linux/') or name.startswith('mac/'):
                    platform_in_zip = name.split('/')[0]
                    if platform_in_zip not in existing_platforms:
                        existing_platforms.append(platform_in_zip)

        if existing_platforms:
            print(f"[INFO] Zip already contains: {', '.join(existing_platforms)}")
            if platform_name in existing_platforms:
                print(f"[INFO] {platform_name} platform already exists, will be replaced")
    else:
        print("[INFO] Creating new multi-platform zip file...")

    # Create/update zip file
    print(f"[INFO] Packaging {platform_name} Chromium into zip...")
    print(f"    Source: {chromium_source_dir}")
    print("    This may take a few minutes (~150MB per platform)...")

    total_files = sum(1 for _ in chromium_source_dir.rglob('*') if _.is_file())
    processed = 0

    # Handle existing zip: remove old platform folder if updating
    if zip_path.exists() and platform_name in existing_platforms:
        print(f"[INFO] Removing existing {platform_name} platform from zip...")
        temp_zip = zip_path.with_suffix('.zip.tmp')
        with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as new_zip:
            with zipfile.ZipFile(zip_path, 'r') as old_zip:
                for item in old_zip.infolist():
                    if not item.filename.startswith(f'{platform_name}/'):
                        new_zip.writestr(item, old_zip.read(item.filename))
        zip_path.unlink()
        temp_zip.rename(zip_path)
        # After removing old platform, use append mode to add new one
        mode = 'a'
    else:
        # New zip or platform doesn't exist yet
        mode = 'a' if zip_path.exists() else 'w'

    # Add/update platform folder in zip
    with zipfile.ZipFile(zip_path, mode, zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
        for root, dirs, files in os.walk(chromium_source_dir):
            for file in files:
                file_path = Path(root) / file
                # Use platform-specific path: {platform_name}/...
                relative_path = file_path.relative_to(chromium_source_dir)
                arcname = f"{platform_name}/{relative_path}"
                zipf.write(file_path, arcname)
                processed += 1
                if processed % 100 == 0:
                    print(f"    Progress: {processed}/{total_files} files...", end='\r')

    # Final summary
    if zip_path.exists():
        zip_size_mb = zip_path.stat().st_size / (1024*1024)
        print(f"\n{'='*60}")
        print("[SUCCESS] Multi-platform packaging complete!")
        print(f"{'='*60}")
        print(f"[INFO] Zip file: {zip_path}")
        print(f"[INFO] Total size: {zip_size_mb:.1f} MB")
        print()

        # Check final platforms in zip
        final_platforms = []
        with zipfile.ZipFile(zip_path, 'r') as final_zip:
            for name in final_zip.namelist():
                if '/' in name:
                    platform_in_zip = name.split('/')[0]
                    if platform_in_zip in ['windows', 'linux', 'mac'] and platform_in_zip not in final_platforms:
                        final_platforms.append(platform_in_zip)

        if final_platforms:
            print(f"[SUCCESS] Zip contains platforms: {', '.join(sorted(final_platforms))}")
        else:
            print("[WARNING] No platforms were successfully packaged")
            return False

        print()
        print("[INFO] Next steps:")
        print("    1. Upload browsers/chromium.zip to your server")
        print("    2. Run: python scripts/setup.py")
        print("    3. Setup will automatically extract the correct platform")

        return True
    else:
        print("[ERROR] Failed to create zip file")
        return False

if __name__ == "__main__":
    success = package_chromium()
    sys.exit(0 if success else 1)

