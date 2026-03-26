#!/usr/bin/env python3
"""
Dashboard and IP geolocation assets installer for MindGraph.

Installs:
  - Python: py-ip2region (for runtime lookups; asked interactively)
  - Static dashboard: ECharts bundle + China GeoJSON under static/js and static/data
  - Embeds china-geo.json into static/js/public-dashboard.js when that file exists
  - ip2region xdb databases (data/ip2region_v4.xdb, optional v6) per services/auth/ip_geolocation.py
  - Patch cache (data/ip2region_patches_cache.json) from data/ip2region_issue/*.fix

Usage (from repository root):
    python scripts/setup/dashboard_install.py

The script asks yes/no questions. For automation: MINDGRAPH_NON_INTERACTIVE=1 (sensible defaults).

See also: scripts/setup/setup_ip2region.md
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _stdin_is_tty() -> bool:
    """True if stdin is an interactive terminal."""
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def _non_interactive_env() -> bool:
    """MINDGRAPH_NON_INTERACTIVE=1 skips prompts (CI / pipes)."""
    value = os.environ.get("MINDGRAPH_NON_INTERACTIVE", "").strip().lower()
    return value in ("1", "true", "yes")


def prompt_yes_no(message: str, default: bool = False) -> bool:
    """
    Ask a yes/no question. Empty input uses default.

    Returns:
        True for yes, False for no.
    """
    tag = "Y/n" if default else "y/N"
    try:
        line = input(f"{message} [{tag}]: ").strip().lower()
    except EOFError:
        return default
    if not line:
        return default
    return line in ("y", "yes", "1", "true")


@dataclass
class DashboardInstallOptions:
    """Resolved options from prompts or non-interactive defaults."""

    project_root: Path
    skip_pip: bool
    force: bool
    skip_dashboard: bool
    skip_embed: bool
    skip_ip2region_db: bool
    with_ipv6: bool
    skip_patches: bool
    verbose: bool


def resolve_project_root_path(script_dir: str, non_interactive: bool) -> Path:
    """Interactive path override or auto-detect from requirements.txt."""
    env_root = os.environ.get("MINDGRAPH_PROJECT_ROOT", "").strip()
    if env_root:
        return Path(os.path.abspath(env_root))
    if non_interactive:
        return Path(resolve_project_root(script_dir))
    print("\nRepository root must contain requirements.txt.")
    try:
        line = input("Path to project root [Enter = auto-detect]: ").strip()
    except EOFError:
        return Path(resolve_project_root(script_dir))
    if line:
        return Path(os.path.abspath(line))
    return Path(resolve_project_root(script_dir))


def resolve_dashboard_install_options(script_dir: str) -> DashboardInstallOptions:
    """Prompt for each option, or use defaults when non-interactive."""
    non_interactive = not _stdin_is_tty() or _non_interactive_env()
    project_root = resolve_project_root_path(script_dir, non_interactive)

    if non_interactive:
        print(
            "[INFO] Non-interactive (pipe or MINDGRAPH_NON_INTERACTIVE=1): "
            "install pip package, dashboard assets, ip2region v4, patches; "
            "skip IPv6 xdb (large); no force."
        )
        return DashboardInstallOptions(
            project_root=project_root,
            skip_pip=False,
            force=False,
            skip_dashboard=False,
            skip_embed=False,
            skip_ip2region_db=False,
            with_ipv6=False,
            skip_patches=False,
            verbose=False,
        )

    print("\n--- Dashboard & ip2region installer ---")
    print("Answer each question; Enter accepts the default in brackets.\n")

    skip_pip = not prompt_yes_no("Install py-ip2region via pip", default=True)
    force = prompt_yes_no("Re-download files that already exist (replace on disk)", default=False)
    skip_dashboard = not prompt_yes_no(
        "Download ECharts and China GeoJSON into static/", default=True
    )
    skip_embed = True
    if not skip_dashboard:
        skip_embed = not prompt_yes_no(
            "Embed china-geo into static/js/public-dashboard.js if that file exists",
            default=True,
        )
    skip_ip2region_db = not prompt_yes_no(
        "Download ip2region .xdb files into data/", default=True
    )
    with_ipv6 = False
    if not skip_ip2region_db:
        with_ipv6 = prompt_yes_no(
            "Also download IPv6 ip2region database (~35 MB)", default=False
        )
    skip_patches = not prompt_yes_no(
        "Build patch cache from data/ip2region_issue/*.fix", default=True
    )
    verbose = prompt_yes_no("Run patch lookup self-test after building cache", default=False)

    return DashboardInstallOptions(
        project_root=project_root,
        skip_pip=skip_pip,
        force=force,
        skip_dashboard=skip_dashboard,
        skip_embed=skip_embed,
        skip_ip2region_db=skip_ip2region_db,
        with_ipv6=with_ipv6,
        skip_patches=skip_patches,
        verbose=verbose,
    )

# -----------------------------------------------------------------------------
# Paths & URLs
# -----------------------------------------------------------------------------

ECHARTS_URL = "https://cdn.jsdelivr.net/npm/echarts@5.6.0/dist/echarts.min.js"
CHINA_GEOJSON_URL = (
    "https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json"
)

IP2REGION_V4_URLS = [
    "https://cdn.jsdelivr.net/gh/lionsoul2014/ip2region@master/data/ip2region_v4.xdb",
    "https://raw.githubusercontent.com/lionsoul2014/ip2region/master/data/ip2region_v4.xdb",
]
IP2REGION_V6_URLS = [
    "https://cdn.jsdelivr.net/gh/lionsoul2014/ip2region@master/data/ip2region_v6.xdb",
    "https://raw.githubusercontent.com/lionsoul2014/ip2region/master/data/ip2region_v6.xdb",
]

PATCHES_DIR_NAME = "data/ip2region_issue"
PATCHES_CACHE_NAME = "data/ip2region_patches_cache.json"

# Reject tiny/corrupt downloads (e.g. CDN HTML error body)
MIN_IP2REGION_V4_BYTES = 1_000_000
MIN_IP2REGION_V6_BYTES = 10_000_000


def resolve_project_root(start_dir: str) -> str:
    """Directory containing requirements.txt (repo root)."""
    current = os.path.abspath(start_dir)
    for _ in range(8):
        if os.path.isfile(os.path.join(current, "requirements.txt")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return os.path.abspath(start_dir)


def http_download(url: str, dest: Path, timeout: int = 300) -> bool:
    """Download binary or text from URL to dest; return True on success."""
    print(f"  GET {url[:80]}...")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "MindGraph-dashboard-install/1"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            with open(dest, "wb") as outfile:
                shutil.copyfileobj(response, outfile)
        print(f"  OK -> {dest} ({dest.stat().st_size / 1024 / 1024:.2f} MB)")
        return True
    except (OSError, urllib.error.URLError, ValueError) as exc:
        print(f"  FAILED: {exc}")
        return False


def download_first_success(urls: List[str], dest: Path, timeout: int) -> bool:
    """Try each URL in order; return True after the first successful download."""
    for url in urls:
        if http_download(url, dest, timeout=timeout):
            return True
    return False


def _xdb_file_plausible(path: Path, min_bytes: int) -> bool:
    """After a fresh download: true if file looks like a real xdb; drop bad blobs."""
    if not path.is_file():
        return False
    size = path.stat().st_size
    if size < min_bytes:
        print(
            f"[ERROR] {path.name} is only {size} bytes "
            f"(expected >= {min_bytes}); delete and retry or check network."
        )
        try:
            path.unlink()
        except OSError:
            pass
        return False
    return True


def _existing_ip2_xdb_ok(path: Path, min_bytes: int) -> bool:
    """
    User-supplied or pre-existing file on disk: large enough to skip re-download.

    Does not delete the file; choose re-download when prompted or delete manually.
    """
    if not path.is_file():
        return False
    size = path.stat().st_size
    if size < min_bytes:
        print(
            f"[WARNING] {path.name} exists ({size} bytes) but expected >= {min_bytes}; "
            "remove it or run again and choose to re-download existing files."
        )
        return False
    return True


def write_data_version(data_dir: Path, note: str) -> None:
    """Single-line timestamp for ip_geolocation._check_database_age."""
    version_path = data_dir / "ip2region.version"
    with open(version_path, "w", encoding="utf-8") as handle:
        handle.write(f"{datetime.now().isoformat()}\n{note}\n")


def ensure_py_ip2region(skip: bool) -> bool:
    """Install py-ip2region via pip unless skip is True."""
    if skip:
        print("[INFO] Skipping pip install (you declined)")
        return True
    print("[INFO] pip install py-ip2region (runtime dependency)...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "py-ip2region>=3.0.2"],
        check=False,
    )
    if result.returncode != 0:
        print("[WARNING] pip install py-ip2region failed; install requirements.txt manually")
        return False
    return True


def install_dashboard_static(project_root: Path, force: bool) -> bool:
    """ECharts + China GeoJSON for static HTML dashboard assets."""
    js_dir = project_root / "static" / "js"
    data_dir = project_root / "static" / "data"
    js_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    echarts_path = js_dir / "echarts.min.js"
    china_path = data_dir / "china-geo.json"

    ok = True
    if force or not echarts_path.exists():
        if not http_download(ECHARTS_URL, echarts_path, timeout=120):
            print("[WARNING] ECharts download failed; map widgets may break.")
            ok = False
    else:
        print(f"[OK] {echarts_path.name} already present")

    if force or not china_path.exists():
        if not http_download(CHINA_GEOJSON_URL, china_path, timeout=120):
            print("[WARNING] China GeoJSON download failed.")
            ok = False
    else:
        print(f"[OK] {china_path.name} already present")

    return ok


def _replace_china_geo_placeholder(js_content: str, geo_json_str: str) -> tuple[str, bool]:
    """Replace chinaGeoJSON null placeholder with embedded JSON."""
    old_a = "let chinaGeoJSON = null;"
    old_b = "var chinaGeoJSON = null;"
    new_decl = f"const chinaGeoJSON = {geo_json_str};"
    if old_a in js_content:
        return js_content.replace(old_a, new_decl), True
    if old_b in js_content:
        return js_content.replace(old_b, new_decl), True
    lines = js_content.split("\n")
    for idx, line in enumerate(lines):
        if "chinaGeoJSON" in line and "null" in line:
            lines[idx] = new_decl
            return "\n".join(lines), True
    return js_content, False


def _strip_load_china_geo_function(js_content: str) -> str:
    """Remove loadChinaGeoJSON async function and its call sites."""
    if "async function loadChinaGeoJSON()" in js_content:
        start = js_content.find("async function loadChinaGeoJSON()")
        if start >= 0:
            func_lines = js_content[start:].split("\n")
            brace_count = 0
            in_function = False
            end_offset = 0
            for i, line in enumerate(func_lines):
                if "async function loadChinaGeoJSON()" in line:
                    in_function = True
                if in_function:
                    brace_count += line.count("{") - line.count("}")
                    if brace_count == 0 and i > 0:
                        end_offset = start + len("\n".join(func_lines[: i + 1]))
                        break
            if end_offset > start:
                js_content = js_content[:start] + js_content[end_offset + 1 :]
    return (
        js_content.replace("await loadChinaGeoJSON();", "").replace(
            "loadChinaGeoJSON();", ""
        )
    )


def embed_china_geo(project_root: Path) -> bool:
    """Embed china-geo.json into public-dashboard.js when present."""
    china_path = project_root / "static" / "data" / "china-geo.json"
    js_path = project_root / "static" / "js" / "public-dashboard.js"
    if not js_path.is_file():
        msg = (
            "[INFO] No static/js/public-dashboard.js — skip embed "
            "(Vue app uses npm echarts)."
        )
        print(msg)
        return True
    if not china_path.is_file():
        print(f"[WARNING] Missing {china_path}; run without --skip-dashboard first.")
        return False

    with open(china_path, "r", encoding="utf-8") as handle:
        geo_data = json.load(handle)
    geo_json_str = json.dumps(geo_data, ensure_ascii=False, separators=(",", ":"))

    with open(js_path, "r", encoding="utf-8") as handle:
        js_content = handle.read()

    js_content, replaced = _replace_china_geo_placeholder(js_content, geo_json_str)
    if not replaced:
        print("[WARNING] Could not find chinaGeoJSON placeholder in public-dashboard.js")
        return False

    js_content = _strip_load_china_geo_function(js_content)

    with open(js_path, "w", encoding="utf-8") as handle:
        handle.write(js_content)

    print(f"[SUCCESS] Embedded china geo into {js_path.name} ({len(geo_json_str):,} chars)")
    return True


def ip_to_int(ip: str) -> int:
    """Return IPv4 address as int, or 0 if invalid."""
    try:
        return int(ipaddress.IPv4Address(ip))
    except ValueError:
        return 0


def _patch_record(
    patch_path: Path,
    line_num: int,
    parts: List[str],
) -> Optional[Dict[str, Any]]:
    """Build one patch dict from pipe-separated fields, or None if invalid."""
    start_ip = parts[0].strip()
    end_ip = parts[1].strip()
    start_int = ip_to_int(start_ip)
    end_int = ip_to_int(end_ip)
    if start_int <= 0 or end_int <= 0:
        return None
    return {
        "start_ip": start_ip,
        "end_ip": end_ip,
        "start_int": start_int,
        "end_int": end_int,
        "country": parts[2].strip(),
        "province": parts[3].strip(),
        "city": parts[4].strip(),
        "isp": parts[5].strip(),
        "source": patch_path.name,
        "line": line_num,
    }


def parse_patch_file(patch_path: Path) -> List[Dict[str, Any]]:
    """Parse one .fix file into patch records (IPv4 ranges)."""
    patches: List[Dict[str, Any]] = []
    encodings = ("utf-8", "gbk", "gb2312", "utf-8-sig")
    content: Optional[str] = None
    for enc in encodings:
        try:
            with open(patch_path, "r", encoding=enc) as handle:
                content = handle.read()
                break
        except UnicodeDecodeError:
            continue
    if content is None:
        print(f"[WARNING] Could not decode {patch_path}")
        return patches

    for line_num, raw in enumerate(content.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) < 6:
            continue
        try:
            rec = _patch_record(patch_path, line_num, parts)
            if rec:
                patches.append(rec)
        except (TypeError, ValueError) as exc:
            print(f"[WARNING] Invalid IP range {patch_path.name}:{line_num}: {exc}")
    return patches


def build_patch_cache(project_root: Path) -> Optional[Dict[str, Any]]:
    """Merge data/ip2region_issue/*.fix into data/ip2region_patches_cache.json."""
    patches_dir = project_root / PATCHES_DIR_NAME
    cache_path = project_root / PATCHES_CACHE_NAME
    if not patches_dir.is_dir():
        print(f"[INFO] No patch directory: {patches_dir}")
        return None
    patch_files = sorted(patches_dir.glob("*.fix"))
    if not patch_files:
        print(f"[INFO] No .fix files in {patches_dir}")
        return None

    print(f"[INFO] Building patch cache from {len(patch_files)} file(s)...")
    all_patches: List[Dict[str, Any]] = []
    for pf in patch_files:
        entries = parse_patch_file(pf)
        print(f"  {pf.name}: {len(entries)} entries")
        all_patches.extend(entries)

    sorted_patches = sorted(all_patches, key=lambda x: x["start_int"])
    cache_data: Dict[str, Any] = {
        "patches": sorted_patches,
        "total_patches": len(sorted_patches),
        "last_updated": datetime.now().isoformat(),
        "patch_files": [p.name for p in patch_files],
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(cache_data, handle, ensure_ascii=False, indent=2)
    print(f"[SUCCESS] Patch cache -> {cache_path} ({len(sorted_patches)} ranges)")
    return cache_data


def find_patch_for_ip(ip: str, cache: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Binary search for a patch covering the given IPv4 string."""
    patches = cache.get("patches", [])
    if not patches:
        return None
    try:
        ip_int = ip_to_int(ip)
        if ip_int == 0:
            return None
        left, right = 0, len(patches) - 1
        while left <= right:
            mid = (left + right) // 2
            patch = patches[mid]
            start_int = patch.get("start_int", 0)
            end_int = patch.get("end_int", 0)
            if start_int <= ip_int <= end_int:
                return {
                    "province": patch.get("province", ""),
                    "city": patch.get("city", ""),
                    "country": patch.get("country", "中国"),
                    "isp": patch.get("isp", ""),
                }
            if ip_int < start_int:
                right = mid - 1
            else:
                left = mid + 1
    except (KeyError, TypeError, ValueError):
        return None
    return None


def verbose_patch_selftest(cache: Dict[str, Any]) -> None:
    """Print sample patch lookups for debugging."""
    for test_ip in ("39.144.0.1", "39.144.10.5", "39.144.177.100"):
        hit = find_patch_for_ip(test_ip, cache)
        if hit:
            print(f"  patch lookup {test_ip} -> {hit.get('province')}, {hit.get('city')}")
        else:
            print(f"  patch lookup {test_ip} -> (use xdb)")


def _ensure_ip2region_v4(data_dir: Path, v4_path: Path, force: bool) -> bool:
    """Download or verify IPv4 xdb; return False if required file missing or bad."""
    if not force and v4_path.is_file():
        if _existing_ip2_xdb_ok(v4_path, MIN_IP2REGION_V4_BYTES):
            print(
                f"[INFO] {v4_path.name} already present — skipping download "
                "(run again and choose re-download to replace)"
            )
            return True
        return False

    if not download_first_success(IP2REGION_V4_URLS, v4_path, timeout=300):
        print("[ERROR] Could not download ip2region_v4.xdb")
        return False
    if not _xdb_file_plausible(v4_path, MIN_IP2REGION_V4_BYTES):
        return False
    write_data_version(data_dir, "ip2region_v4.xdb")
    return True


def _ensure_ip2region_v6_optional(data_dir: Path, v6_path: Path, force: bool) -> None:
    """Download or verify IPv6 xdb (optional)."""
    if not force and v6_path.is_file():
        if _existing_ip2_xdb_ok(v6_path, MIN_IP2REGION_V6_BYTES):
            print(
                f"[INFO] {v6_path.name} already present — skipping download "
                "(run again and choose re-download to replace)"
            )
        return

    if not download_first_success(IP2REGION_V6_URLS, v6_path, timeout=600):
        print("[WARNING] IPv6 xdb download failed (optional).")
        return
    if not _xdb_file_plausible(v6_path, MIN_IP2REGION_V6_BYTES):
        print("[WARNING] IPv6 xdb file looks corrupt; removed (optional).")
        return
    write_data_version(data_dir, "ip2region_v6.xdb")


def install_ip2region_xdb(
    project_root: Path,
    force: bool,
    with_ipv6: bool,
) -> bool:
    """Download ip2region_v4.xdb (required) and optional v6 to data/."""
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    v4_path = data_dir / "ip2region_v4.xdb"
    v6_path = data_dir / "ip2region_v6.xdb"

    v4_ok = _ensure_ip2region_v4(data_dir, v4_path, force)
    if with_ipv6:
        _ensure_ip2region_v6_optional(data_dir, v6_path, force)
    else:
        print("[INFO] Skipping IPv6 xdb (not selected)")

    return v4_ok


def parse_dashboard_args() -> None:
    """Parse CLI for dashboard_install.py (--help only; options come from prompts)."""
    parser = argparse.ArgumentParser(
        description=(
            "Install dashboard static assets, ip2region xdb DBs, and patch cache."
        ),
        epilog=(
            "Interactive prompts choose each step. "
            "Set MINDGRAPH_NON_INTERACTIVE=1 to skip prompts. "
            "Set MINDGRAPH_PROJECT_ROOT to override the repo path."
        ),
    )
    parser.parse_args()


def main() -> int:
    """Run dashboard and ip2region setup steps; exit code 0 on success."""
    parse_dashboard_args()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    opts = resolve_dashboard_install_options(script_dir)
    project_root = opts.project_root
    print(f"[INFO] Project root: {project_root}")

    os.chdir(project_root)

    ensure_py_ip2region(opts.skip_pip)

    if not opts.skip_dashboard:
        print("\n--- Dashboard static (ECharts + GeoJSON) ---")
        install_dashboard_static(project_root, opts.force)
        if not opts.skip_embed:
            print("\n--- Embed China GeoJSON ---")
            if not embed_china_geo(project_root):
                return 1
    else:
        print("[INFO] Skipping dashboard static (you declined)")

    if not opts.skip_ip2region_db:
        print("\n--- ip2region xdb ---")
        if not install_ip2region_xdb(project_root, opts.force, opts.with_ipv6):
            return 1
    else:
        print("[INFO] Skipping ip2region xdb (you declined)")

    if not opts.skip_patches:
        print("\n--- ip2region patches ---")
        cache = build_patch_cache(project_root)
        if cache and opts.verbose:
            verbose_patch_selftest(cache)
    else:
        print("[INFO] Skipping patches (you declined)")

    print("\n[DONE] dashboard_install.py finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
