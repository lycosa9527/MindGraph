#!/usr/bin/env python3
"""
Download AbuseIPDB /blacklist into data/abuseipdb/blacklist_baseline.txt

Requires ABUSEIPDB_API_KEY in the environment (e.g. from .env via python-dotenv).
Uses the same parameters as the app: confidence minimum and limit from env or defaults.

AbuseIPDB does not expose the entire database: the blacklist is capped by subscription
(Standard 10k / Basic 100k / Premium 500k). Default limit is 10000 (Free/Standard).
Set ABUSEIPDB_BLACKLIST_LIMIT higher if your plan allows (API truncates to your cap).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


# Project imports (run from repo root: python scripts/setup/download_abuseipdb_baseline.py)
sys.path.insert(0, str(_project_root()))

from services.infrastructure.security.abuseipdb_blacklist_parse import (
    parse_abuseipdb_blacklist_plaintext,
)
from services.infrastructure.security.abuseipdb_service import get_abuseipdb_api_base


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def main() -> int:
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("python-dotenv is required", file=sys.stderr)
        return 1

    load_dotenv(_project_root() / ".env")

    api_key = os.getenv("ABUSEIPDB_API_KEY", "").strip()
    if not api_key:
        print("Set ABUSEIPDB_API_KEY in .env", file=sys.stderr)
        return 1

    try:
        import httpx
    except ImportError:
        print("httpx is required", file=sys.stderr)
        return 1

    conf = max(25, min(100, _env_int("ABUSEIPDB_BLACKLIST_CONFIDENCE_MINIMUM", 75)))
    limit = max(1, min(500_000, _env_int("ABUSEIPDB_BLACKLIST_LIMIT", 10_000)))

    url = f"{get_abuseipdb_api_base()}/blacklist"
    params = {"confidenceMinimum": conf, "limit": limit}
    headers = {"Key": api_key, "Accept": "text/plain"}

    with httpx.Client(timeout=600.0) as client:
        response = client.get(url, headers=headers, params=params)

    if response.status_code != 200:
        print("HTTP", response.status_code, response.text[:500], file=sys.stderr)
        return 1

    body = response.text or ""
    ips = parse_abuseipdb_blacklist_plaintext(body)
    if not ips and body.strip().startswith("{"):
        print("Unexpected response (expected plaintext IPs):", body[:500], file=sys.stderr)
        return 1

    lines: list[str] = [
        "# Downloaded by scripts/setup/download_abuseipdb_baseline.py",
        f"# confidenceMinimum={conf} limit={limit}",
        "#",
    ]
    for ip in sorted(ips):
        lines.append(ip)

    out_path = _project_root() / "data" / "abuseipdb" / "blacklist_baseline.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(lines) - 3} IPs to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
