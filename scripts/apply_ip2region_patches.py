#!/usr/bin/env python3
"""
Apply ip2region database patches from data/ip2region_issue folder.

This script loads patches and creates an override system that checks patches
before querying the main xdb database. Patches take priority over the database.

Based on Java implementation pattern from:
https://github.com/lionsoul2014/ip2region/tree/master/maker/java#xdb-%E6%95%B0%E6%8D%AE%E7%BC%96%E8%BE%91

Usage:
    python scripts/apply_ip2region_patches.py
"""

import json
import ipaddress
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# Paths
PATCHES_DIR = Path("data/ip2region_issue")
PATCHES_CACHE = Path("data/ip2region_patches_cache.json")
PATCHES_LOG = Path("data/ip2region_patches.log")


def ip_to_int(ip: str) -> int:
    """Convert IP address to integer."""
    try:
        return int(ipaddress.IPv4Address(ip))
    except ValueError:
        return 0


def parse_patch_file(patch_path: Path) -> List[Dict]:
    """
    Parse patch file format: start_ip|end_ip|Country|Province|City|ISP

    Returns list of patch entries with IP ranges converted to integers.
    """
    patches = []
    try:
        # Try UTF-8 first, fallback to GBK/GB2312 for Windows compatibility
        encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']
        content = None

        for enc in encodings:
            try:
                with open(patch_path, 'r', encoding=enc) as f:
                    content = f.read()
                    break
            except UnicodeDecodeError:
                continue

        if content is None:
            print(f"Warning: Could not decode {patch_path} with any encoding")
            return patches

        # Process lines
        for line_num, line in enumerate(content.splitlines(), 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Format: start_ip|end_ip|Country|Province|City|ISP
            parts = line.split('|')
            if len(parts) >= 6:
                start_ip = parts[0].strip()
                end_ip = parts[1].strip()
                country = parts[2].strip()
                province = parts[3].strip()
                city = parts[4].strip()
                isp = parts[5].strip()

                # Convert IPs to integers for range checking
                try:
                    start_int = ip_to_int(start_ip)
                    end_int = ip_to_int(end_ip)

                    if start_int > 0 and end_int > 0:
                        patches.append({
                            'start_ip': start_ip,
                            'end_ip': end_ip,
                            'start_int': start_int,
                            'end_int': end_int,
                            'country': country,
                            'province': province,
                            'city': city,
                            'isp': isp,
                            'source': patch_path.name,
                            'line': line_num
                        })
                except Exception as e:
                    print(f"Warning: Invalid IP range in {patch_path.name} line {line_num}: {e}")
                    continue

    except Exception as e:
        print(f"Error parsing {patch_path}: {e}")

    return patches


def build_patch_cache() -> Dict:
    """
    Build a cache of all patches for fast lookup.

    Returns a dictionary mapping IP ranges to location data.
    """
    if not PATCHES_DIR.exists():
        print(f"Patch directory not found: {PATCHES_DIR}")
        return {}

    # Find all patch files
    patch_files = list(PATCHES_DIR.glob("*.fix"))
    if not patch_files:
        print(f"No patch files found in {PATCHES_DIR}")
        return {}

    print(f"Found {len(patch_files)} patch file(s):")
    for pf in patch_files:
        print(f"  - {pf.name}")

    # Parse all patches
    all_patches = []
    for patch_file in patch_files:
        patches = parse_patch_file(patch_file)
        print(f"  Parsed {len(patches)} entries from {patch_file.name}")
        all_patches.extend(patches)

    print(f"\nTotal patches: {len(all_patches)}")

    # Build cache structure: list of patches sorted by start_int for binary search
    patches_sorted = sorted(all_patches, key=lambda x: x['start_int'])

    # Save to cache file with proper UTF-8 encoding
    cache_data = {
        'patches': patches_sorted,
        'total_patches': len(patches_sorted),
        'last_updated': datetime.now().isoformat(),
        'patch_files': [pf.name for pf in patch_files]
    }

    # Ensure UTF-8 encoding with BOM for Windows compatibility
    with open(PATCHES_CACHE, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)

    print(f"\nPatch cache saved to: {PATCHES_CACHE}")
    print(f"Total patches cached: {len(patches_sorted)}")

    return cache_data


def load_patch_cache() -> Dict:
    """Load patch cache from file."""
    if not PATCHES_CACHE.exists():
        return {}

    try:
        with open(PATCHES_CACHE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading patch cache: {e}")
        return {}


def find_patch_for_ip(ip: str, cache: Dict) -> Optional[Dict]:
    """
    Find patch entry for a given IP address using binary search.

    Returns patch data if IP falls within any patch range, None otherwise.
    """
    patches = cache.get('patches', [])
    if not patches:
        return None

    try:
        ip_int = ip_to_int(ip)
        if ip_int == 0:
            return None

        # Binary search for matching range
        left, right = 0, len(patches) - 1

        while left <= right:
            mid = (left + right) // 2
            patch = patches[mid]

            start_int = patch.get('start_int', 0)
            end_int = patch.get('end_int', 0)

            if start_int <= ip_int <= end_int:
                # Found matching range - return location data
                return {
                    'province': patch.get('province', ''),
                    'city': patch.get('city', ''),
                    'country': patch.get('country', '中国'),
                    'isp': patch.get('isp', '')
                }
            elif ip_int < start_int:
                right = mid - 1
            else:
                left = mid + 1

        return None

    except Exception as e:
        print(f"Error finding patch for IP {ip}: {e}")
        import traceback
        traceback.print_exc()
        return None


def apply_patches():
    """Main function to build and apply patches."""
    print("=" * 60)
    print("IP2Region Patch Application Tool")
    print("=" * 60)

    # Build patch cache
    print("\n[1/2] Building patch cache...")
    cache = build_patch_cache()

    if not cache:
        print("\nNo patches found. Exiting.")
        return

    # Test patch lookup
    print("\n[2/2] Testing patch lookup...")
    test_ips = ['39.144.0.1', '39.144.10.5', '39.144.177.100']

    # Set console encoding for Windows to display Chinese correctly
    if sys.platform == 'win32':
        try:
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        except (OSError, AttributeError):
            pass

    for test_ip in test_ips:
        patch = find_patch_for_ip(test_ip, cache)
        if patch:
            province = patch.get('province', '')
            city = patch.get('city', '')
            # Use repr to show actual characters even if console can't display them
            print(f"  {test_ip} -> {province}, {city} (from patch)")
        else:
            print(f"  {test_ip} -> No patch found (will use main database)")

    print("\n" + "=" * 60)
    print("Patch application complete!")
    print("\nNext steps:")
    print("1. Patches are now cached and will be checked automatically")
    print("2. The IP geolocation service will use patches when available")
    print("3. Restart the application to load the patch cache")
    print("=" * 60)


if __name__ == "__main__":
    apply_patches()
