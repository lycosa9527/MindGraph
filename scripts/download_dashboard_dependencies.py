#!/usr/bin/env python3
"""
Download Dashboard Dependencies
================================

Downloads ECharts library and China geoJSON for public dashboard.

Usage:
    python scripts/download_dashboard_dependencies.py
"""

import urllib.request
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent
STATIC_JS_DIR = BASE_DIR / "static" / "js"
STATIC_DATA_DIR = BASE_DIR / "static" / "data"

# URLs
ECHARTS_URL = "https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"
CHINA_GEOJSON_URL = "https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json"


def download_file(url: str, filepath: Path):
    """Download a file from URL."""
    print(f"Downloading {filepath.name}...")
    try:
        urllib.request.urlretrieve(url, filepath)
        print(f"Success: Downloaded {filepath.name}")
        return True
    except Exception as e:
        print(f"Failed to download {filepath.name}: {e}")
        return False


def main():
    """Download dashboard dependencies."""
    # Create directories if they don't exist
    STATIC_JS_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Download ECharts
    echarts_path = STATIC_JS_DIR / "echarts.min.js"
    if not echarts_path.exists():
        if not download_file(ECHARTS_URL, echarts_path):
            print("Warning: ECharts download failed. Dashboard map will not work.")
            print(f"Please manually download from: {ECHARTS_URL}")
            print(f"Save to: {echarts_path}")
    else:
        print(f"OK: {echarts_path.name} already exists")

    # Download China geoJSON
    china_geo_path = STATIC_DATA_DIR / "china-geo.json"
    if not china_geo_path.exists():
        if not download_file(CHINA_GEOJSON_URL, china_geo_path):
            print("Warning: China geoJSON download failed. Dashboard map will not work.")
            print(f"Please manually download from: {CHINA_GEOJSON_URL}")
            print(f"Save to: {china_geo_path}")
    else:
        print(f"OK: {china_geo_path.name} already exists")

    print("\nDashboard dependencies download complete!")


if __name__ == "__main__":
    main()

