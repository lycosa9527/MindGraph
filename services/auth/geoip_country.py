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

from services.auth.geo_cn_mainland_cookie import GEO_CN_MAINLAND_COOKIE_NAME, verify_geo_cn_mainland_cookie

logger = logging.getLogger(__name__)

# MaxMind GeoLite2 Country (free tier) — download and place MMDB on disk; see log / admin UI.
GEOIP_GEOLITE_DOWNLOAD_URL = "https://dev.maxmind.com/geoip/geolite2-free-geolocation-data/?lang=en"


class _GeoReaderState:
    """Module-level GeoIP reader singleton (lazy, fail-closed on errors)."""

    reader: Optional[geoip2.database.Reader] = None
    unavailable: bool = False


_STATE = _GeoReaderState()


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def get_geolite_country_mmdb_path() -> Path:
    """
    Resolved path to GeoLite2-Country.mmdb.

    Uses GEOIP_MAXMIND_COUNTRY_PATH when set; otherwise project data/GeoLite2-Country.mmdb.
    """
    raw = os.getenv("GEOIP_MAXMIND_COUNTRY_PATH", "").strip()
    if raw:
        return Path(raw)
    return _repo_root() / "data" / "GeoLite2-Country.mmdb"


def is_geolite_country_mmdb_file_present() -> bool:
    """True if the GeoLite2 Country MMDB file exists on disk."""
    return get_geolite_country_mmdb_path().is_file()


def log_geolite_country_mmdb_startup_status() -> None:
    """Log whether GeoLite2 Country MMDB is present (call from main worker at startup)."""
    path = get_geolite_country_mmdb_path()
    if is_geolite_country_mmdb_file_present():
        logger.info("[GeoLite] GeoLite2-Country MMDB found at %s", path)
        return
    logger.warning(
        "[GeoLite] GeoLite2-Country.mmdb is missing at %s. "
        "Download GeoLite Country from %s "
        "and copy GeoLite2-Country.mmdb to that path (or set GEOIP_MAXMIND_COUNTRY_PATH). "
        "Overseas email registration and email-login GeoIP checks require this file.",
        path,
        GEOIP_GEOLITE_DOWNLOAD_URL,
    )


def get_geoip_country_reader() -> Optional[geoip2.database.Reader]:
    """
    Lazy singleton Reader for GeoLite2-Country.mmdb.

    Returns None if the file is missing or cannot be opened.
    """
    if _STATE.unavailable:
        return None
    if _STATE.reader is not None:
        return _STATE.reader
    path = get_geolite_country_mmdb_path()
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


def overseas_email_registration_allowed(
    client_ip: str,
    *,
    request: Optional[Request] = None,
) -> tuple[bool, str, bool]:
    """
    Returns (allowed, error_message_key, stamp_cn_cookie).

    error_message_key is empty when allowed is True.
    When country cannot be resolved (None), allow the overseas email path; callers must
    reject mainland China email domains separately.

    If ``request`` is provided, a signed HttpOnly cookie from a prior CN observation
    blocks registration even when the current IP is not CN (VPN).

    When ``stamp_cn_cookie`` is True, the caller must attach the geo CN cookie to the
    HTTP response (GeoIP currently resolves to CN); use :func:`set_geo_cn_mainland_cookie`
    on the same object returned to the client (e.g. ``JSONResponse``), not only the
    injected ``Response``, or ``Set-Cookie`` is dropped when raising ``HTTPException``.
    """
    if request is not None:
        raw = request.cookies.get(GEO_CN_MAINLAND_COOKIE_NAME)
        if verify_geo_cn_mainland_cookie(raw):
            return False, "registration_email_not_available_in_region", False

    code = lookup_country_iso_code(client_ip)
    if code == "CN":
        return False, "registration_email_not_available_in_region", True
    return True, "", False


def email_cn_geo_blocked(
    client_ip: str,
    request: Optional[Request],
    *,
    whitelisted_from_cn: bool,
) -> tuple[bool, str, bool]:
    """
    Returns (must_deny, message_key, stamp_cn_cookie).

    Blocks when a valid ``mg_geo_cn_mainland`` cookie is present (prior CN observation)
    or when GeoIP resolves to CN (unless ``whitelisted_from_cn``). ``stamp_cn_cookie``
    is True when the current IP is CN so callers can attach ``Set-Cookie`` on 403.

    When ``request`` is set, country uses :func:`resolve_country_iso_from_request`
    (same as VPN policy: CF-IPCountry when present, else MMDB on client IP). When
    ``request`` is omitted (e.g. tests), ``client_ip`` is resolved via MMDB only.

    ``message_key`` is empty when ``must_deny`` is False. Otherwise use
    ``Messages.error`` for ``email_login_blocked_in_mainland_china`` or
    ``login_email_geoip_unavailable``.
    """
    if request is not None:
        raw = request.cookies.get(GEO_CN_MAINLAND_COOKIE_NAME)
        if verify_geo_cn_mainland_cookie(raw):
            return True, "email_login_blocked_in_mainland_china", False

    if whitelisted_from_cn:
        return False, "", False

    if request is not None:
        code = resolve_country_iso_from_request(request)
    else:
        code = lookup_country_iso_code(client_ip)
    if code is None:
        return True, "login_email_geoip_unavailable", False
    if code == "CN":
        return True, "email_login_blocked_in_mainland_china", True
    return False, "", False


def evaluate_email_login_geoip(
    client_ip: str,
    whitelisted_from_cn: bool,
    request: Optional[Request] = None,
) -> tuple[bool, str]:
    """
    Returns (must_deny, message_key).

    Prefer :func:`email_cn_geo_blocked` with a ``Request`` so the CN stamp cookie is
    enforced. When ``request`` is omitted, cookie checks are skipped (tests only).
    """
    must_deny, msg_key, _ = email_cn_geo_blocked(
        client_ip,
        request,
        whitelisted_from_cn=whitelisted_from_cn,
    )
    return must_deny, msg_key
