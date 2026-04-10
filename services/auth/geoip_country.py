"""
GeoLite2 Country MMDB lookup for overseas email registration IP checks.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import geoip2.database
import geoip2.errors
from fastapi import Request

logger = logging.getLogger(__name__)


class _GeoReaderState:
    """Module-level GeoIP reader singleton (lazy, fail-closed on errors)."""

    reader: Optional[geoip2.database.Reader] = None
    unavailable: bool = False


_STATE = _GeoReaderState()


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _mmdb_path() -> Path:
    raw = os.getenv("GEOIP_MAXMIND_COUNTRY_PATH", "").strip()
    if raw:
        return Path(raw)
    return _repo_root() / "data" / "GeoLite2-Country.mmdb"


def get_geoip_country_reader() -> Optional[geoip2.database.Reader]:
    """
    Lazy singleton Reader for GeoLite2-Country.mmdb.

    Returns None if the file is missing or cannot be opened.
    """
    if _STATE.unavailable:
        return None
    if _STATE.reader is not None:
        return _STATE.reader
    path = _mmdb_path()
    if not path.is_file():
        logger.warning("GeoLite2 Country MMDB not found at %s", path)
        _STATE.unavailable = True
        return None
    try:
        _STATE.reader = geoip2.database.Reader(str(path))
    except OSError as exc:
        logger.warning("Could not open GeoIP MMDB at %s: %s", path, exc)
        _STATE.unavailable = True
        return None
    return _STATE.reader


def resolve_country_iso_from_request(request: Request) -> Optional[str]:
    """
    Prefer Cloudflare CF-IPCountry when present; otherwise GeoIP lookup on client IP.

    Args:
        request: FastAPI request (must be imported at runtime, not only TYPE_CHECKING).

    Returns:
        ISO 3166-1 alpha-2 country code, or None if indeterminate.
    """
    from utils.auth import get_client_ip

    cf_raw = request.headers.get("CF-IPCountry") or request.headers.get("cf-ipcountry")
    if cf_raw:
        candidate = cf_raw.strip().upper()
        if len(candidate) == 2 and candidate.isalpha():
            return candidate

    return lookup_country_iso_code(get_client_ip(request))


def lookup_country_iso_code(client_ip: str) -> Optional[str]:
    """
    Return ISO 3166-1 alpha-2 country code, or None if indeterminate (fail-closed).

    None means: missing/invalid IP, MMDB missing, address not found, or empty code.
    """
    if not client_ip or client_ip == "unknown":
        return None

    reader = get_geoip_country_reader()
    if reader is None:
        return None

    try:
        response = reader.country(client_ip)
        code = response.country.iso_code
    except geoip2.errors.AddressNotFoundError:
        return None
    except (ValueError, OSError) as exc:
        logger.debug("GeoIP lookup failed for %s: %s", client_ip, exc)
        return None

    if not code:
        return None
    return code


def overseas_email_registration_allowed(client_ip: str) -> tuple[bool, str]:
    """
    Returns (allowed, error_message_key).

    error_message_key is empty when allowed is True.
    When country cannot be resolved (None), allow the overseas email path; callers must
    reject mainland China email domains separately.
    """
    code = lookup_country_iso_code(client_ip)
    if code == "CN":
        return False, "registration_email_not_available_in_region"
    return True, ""


def evaluate_email_login_geoip(
    client_ip: str,
    whitelisted_from_cn: bool,
) -> tuple[bool, str]:
    """
    Returns (must_deny, message_key).

    If must_deny is False, email login may continue. If True, message_key is for
    Messages.error: mainland CN without whitelist (403) or GeoIP unavailable (503).
    """
    if whitelisted_from_cn:
        return False, ""
    code = lookup_country_iso_code(client_ip)
    if code is None:
        return True, "login_email_geoip_unavailable"
    if code == "CN":
        return True, "email_login_blocked_in_mainland_china"
    return False, ""
