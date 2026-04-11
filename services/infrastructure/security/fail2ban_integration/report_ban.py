"""
CLI: report a banned IP to AbuseIPDB (for Fail2ban action.d).

Usage (from MindGraph repo root, with PYTHONPATH=. or venv):
  python -m services.infrastructure.security.fail2ban_integration.report_ban <ip>

Environment:
  ABUSEIPDB_API_KEY_FILE — default /etc/fail2ban/abuseipdb.conf (lines KEY=...)
  Or ABUSEIPDB_API_KEY for testing.
"""

from __future__ import annotations

import argparse
import ipaddress
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from services.infrastructure.security.abuseipdb_service import (
    CATEGORY_BRUTE_FORCE,
    client_ip_is_skipped_for_abuseipdb,
    report_ip_abuse_sync,
)

logger = logging.getLogger(__name__)

DEFAULT_KEY_FILE = "/etc/fail2ban/abuseipdb.conf"


def _read_key_file(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.upper().startswith("KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def normalize_client_ip(text: str) -> str:
    """Return canonical IP string or raise ValueError."""
    addr = ipaddress.ip_address(text.split("%")[0].strip())
    return str(addr)


def load_api_key() -> str:
    env_key = os.getenv("ABUSEIPDB_API_KEY", "").strip()
    if env_key:
        return env_key

    key_path = os.getenv("ABUSEIPDB_API_KEY_FILE", DEFAULT_KEY_FILE)
    key = _read_key_file(Path(key_path))
    if key:
        return key

    print("AbuseIPDB API key not found. Set ABUSEIPDB_API_KEY or create", key_path, file=sys.stderr)
    sys.exit(2)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Report banned IP to AbuseIPDB")
    parser.add_argument("ip", help="IPv4/IPv6 address Fail2ban banned")
    args = parser.parse_args()

    try:
        ip_normalized = normalize_client_ip(args.ip)
    except ValueError:
        print("Invalid IP address:", args.ip.strip(), file=sys.stderr)
        sys.exit(2)

    if client_ip_is_skipped_for_abuseipdb(ip_normalized):
        print("Skipping AbuseIPDB report for private or loopback IP", ip_normalized)
        sys.exit(0)

    api_key = load_api_key()

    comment = "MindGraph Fail2ban: automated report on ban action"
    ok = report_ip_abuse_sync(
        ip_normalized,
        str(CATEGORY_BRUTE_FORCE),
        comment,
        api_key,
    )
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
