"""
Parse AbuseIPDB GET /api/v2/blacklist JSON responses.

See https://docs.abuseipdb.com/ — ``data`` is a list of objects with ``ipAddress``.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Set, Tuple


def parse_abuseipdb_blacklist_payload(
    payload: Dict[str, Any],
) -> Tuple[Set[str], Optional[str]]:
    """
    Parse JSON from GET /api/v2/blacklist.

    Docs: ``data`` is a list of objects with ``ipAddress`` (and scores).
    Also accepts legacy ``data.ips`` with ``ip`` / ``ipAddress`` entries.
    """
    data_block = payload.get("data")
    ips: Set[str] = set()

    if isinstance(data_block, list):
        for item in data_block:
            if not isinstance(item, dict):
                continue
            addr = item.get("ipAddress") or item.get("ip")
            if isinstance(addr, str) and addr.strip():
                ips.add(addr.strip())
        return ips, None

    if isinstance(data_block, dict):
        ips_raw = data_block.get("ips")
        if not isinstance(ips_raw, list):
            return set(), "missing ips"
        for item in ips_raw:
            if isinstance(item, dict):
                addr = item.get("ip") or item.get("ipAddress")
                if isinstance(addr, str) and addr.strip():
                    ips.add(addr.strip())
        return ips, None

    return set(), "missing data"


def parse_abuseipdb_blacklist_plaintext(body: str) -> Set[str]:
    """
    Parse newline-separated IPs from GET /blacklist with ``Accept: text/plain``.

    See https://docs.abuseipdb.com/ (plaintext blacklist; large limits supported).
    """
    ips: Set[str] = set()
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            ips.add(stripped)
    return ips
