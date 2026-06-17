#!/usr/bin/env python3
"""
Download CrowdSec Raw IP List into data/crowdsec/blocklist_baseline.txt

Requires CROWDSEC_BLOCKLIST_URL (or INTEGRATION_ID) and
CROWDSEC_BLOCKLIST_USERNAME / CROWDSEC_BLOCKLIST_PASSWORD in the environment
(e.g. from .env via python-dotenv).

Community tiers often allow roughly one successful pull per 24h; do not run this
in a tight loop. See https://docs.crowdsec.net/u/integrations/rawiplist/
"""

from __future__ import annotations

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import httpx
except ImportError:
    httpx = None

import os
import sys

try:
    from _path_setup import project_root
except ModuleNotFoundError:
    from scripts.setup._path_setup import project_root

from services.infrastructure.security import abuseipdb_service
from services.infrastructure.security.crowdsec_blocklist_service import (
    build_crowdsec_blocklist_content_url,
)


def main() -> int:
    """Main."""
    if load_dotenv is None:
        print("python-dotenv is required", file=sys.stderr)
        return 1
    if httpx is None:
        print("httpx is required", file=sys.stderr)
        return 1

    load_dotenv(project_root / ".env")

    url = build_crowdsec_blocklist_content_url()
    user = os.getenv("CROWDSEC_BLOCKLIST_USERNAME", "").strip()
    password = os.getenv("CROWDSEC_BLOCKLIST_PASSWORD", "").strip()

    if not url:
        print(
            "Set CROWDSEC_BLOCKLIST_URL or CROWDSEC_BLOCKLIST_INTEGRATION_ID in .env",
            file=sys.stderr,
        )
        return 1
    if not user or not password:
        print("Set CROWDSEC_BLOCKLIST_USERNAME and CROWDSEC_BLOCKLIST_PASSWORD in .env", file=sys.stderr)
        return 1

    with httpx.Client(timeout=600.0) as client:
        response = client.get(
            url,
            auth=(user, password),
            headers={"Accept": "text/plain"},
        )

    if response.status_code != 200:
        print("HTTP", response.status_code, response.text[:500], file=sys.stderr)
        return 1

    body = response.text or ""
    ips = abuseipdb_service.parse_baseline_file_lines(body)
    if not ips:
        print("No valid IPs in response:", body[:500], file=sys.stderr)
        return 1

    lines: list[str] = [
        "# Downloaded by scripts/setup/download_crowdsec_baseline.py",
        f"# url={url}",
        "#",
    ]
    for ip in sorted(ips):
        lines.append(ip)

    out_path = project_root / "data" / "crowdsec" / "blocklist_baseline.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(lines) - 3} IPs to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
