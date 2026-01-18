#!/usr/bin/env python3
"""
Download ip2region database file.

This script downloads the ip2region database file needed for local IP geolocation.
No external API calls - all lookups are done locally.

Usage:
    python scripts/download_ip2region_db.py
"""

import sys
import urllib.request
import httpx
from pathlib import Path
from datetime import datetime

# Database URLs (multiple sources for fallback)
# ip2region uses .xdb format in v2.x, but the Python package may include .db
# Try multiple sources including mirrors
DB_URLS = [
    # Try Gitee mirror (often faster in China)
    "https://gitee.com/lionsoul/ip2region/raw/master/data/ip2region.db",
    # GitHub raw content (alternative path)
    "https://raw.githubusercontent.com/lionsoul2014/ip2region/master/data/ip2region.db",
    # Try direct GitHub file access
    "https://github.com/lionsoul2014/ip2region/blob/master/data/ip2region.db?raw=true",
    # CDN mirror
    "https://cdn.jsdelivr.net/gh/lionsoul2014/ip2region@master/data/ip2region.db",
]

DB_FILE_PATH = Path("data/ip2region.db")
DB_VERSION_FILE = Path("data/ip2region.version")


def download_database():
    """Download ip2region database file with multiple fallback URLs."""
    print(f"Downloading ip2region database to {DB_FILE_PATH}...")

    # Ensure data directory exists
    DB_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Try each URL
    for i, url in enumerate(DB_URLS, 1):
        try:
            print(f"Trying source {i}/{len(DB_URLS)}: {url}")

            # Use httpx for better async support and timeout handling
            try:
                with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                    response = client.get(url)
                    response.raise_for_status()

                    # Write to file
                    with open(DB_FILE_PATH, 'wb') as f:
                        f.write(response.content)

                    file_size_mb = DB_FILE_PATH.stat().st_size / 1024 / 1024
                    print(f"Success! Database downloaded to {DB_FILE_PATH}")
                    print(f"File size: {file_size_mb:.2f} MB")

                    # Save version info
                    with open(DB_VERSION_FILE, 'w') as f:
                        f.write(f"{datetime.now().isoformat()}\n{url}\n")

                    return True

            except ImportError:
                # Fallback to urllib if httpx not available
                print("httpx not available, using urllib...")
                urllib.request.urlretrieve(url, DB_FILE_PATH)
                file_size_mb = DB_FILE_PATH.stat().st_size / 1024 / 1024
                print(f"Success! Database downloaded to {DB_FILE_PATH}")
                print(f"File size: {file_size_mb:.2f} MB")

                # Save version info
                with open(DB_VERSION_FILE, 'w') as f:
                    f.write(f"{datetime.now().isoformat()}\n{url}\n")

                return True

        except Exception as e:
            print(f"Failed: {e}")
            if i < len(DB_URLS):
                print("Trying next source...")
                continue
            else:
                print("\nAll download sources failed.")
                print("\nManual download instructions:")
                print("1. Visit: https://github.com/lionsoul2014/ip2region")
                print("2. Download ip2region.db from the data/ directory")
                print(f"3. Place it in: {DB_FILE_PATH.absolute()}")
                return False

    return False


def check_database_age():
    """Check how old the database is."""
    if not DB_FILE_PATH.exists():
        return None

    if DB_VERSION_FILE.exists():
        try:
            with open(DB_VERSION_FILE, 'r') as f:
                lines = f.readlines()
                if lines:
                    download_time = datetime.fromisoformat(lines[0].strip())
                    age_days = (datetime.now() - download_time).days
                    return age_days
        except Exception:
            pass

    # Fallback: use file modification time
    try:
        mtime = datetime.fromtimestamp(DB_FILE_PATH.stat().st_mtime)
        age_days = (datetime.now() - mtime).days
        return age_days
    except Exception:
        return None


if __name__ == "__main__":
    # Check if database exists
    if DB_FILE_PATH.exists():
        age_days = check_database_age()
        if age_days is not None:
            print(f"Database exists (downloaded {age_days} days ago)")
        else:
            print(f"Database exists at {DB_FILE_PATH}")

        print("\nNote: IP geolocation databases should be updated monthly for accuracy.")
        response = input("Download/update database? (y/N): ")
        if response.lower() != 'y':
            print("Skipping download.")
            sys.exit(0)
    else:
        print("Database not found. Downloading...")

    success = download_database()
    sys.exit(0 if success else 1)

