# Mirrors chrome-extension/doc-extract/smartedu/token.js — keep token blob shape in sync.

"""DPAPI-backed SmartEdu access token storage."""

from __future__ import annotations

import json

from file_reader.dpapi_store import DpapiError, dpapi_available, protect_bytes, unprotect_bytes
from file_reader.settings import SETTINGS_DIR, SMARTEDU_TOKEN_PATH


def protect_smartedu_token(access_token: str) -> bytes:
    """Serialize and DPAPI-encrypt the SmartEdu token."""
    payload = json.dumps({"access_token": access_token.strip()}, separators=(",", ":")).encode("utf-8")
    return protect_bytes(payload)


def unprotect_smartedu_token(blob: bytes) -> str:
    """DPAPI-decrypt SmartEdu access token."""
    raw = unprotect_bytes(blob).decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise DpapiError("Invalid SmartEdu token payload")
    return str(data.get("access_token") or "")


def load_smartedu_token() -> str:
    """Load saved SmartEdu token or return empty string."""
    if not SMARTEDU_TOKEN_PATH.is_file():
        return ""
    try:
        return unprotect_smartedu_token(SMARTEDU_TOKEN_PATH.read_bytes()).strip()
    except (OSError, DpapiError, json.JSONDecodeError, ValueError):
        return ""


def save_smartedu_token(access_token: str) -> None:
    """Persist SmartEdu token with DPAPI."""
    token = access_token.strip()
    if not token:
        clear_smartedu_token()
        return
    if not dpapi_available():
        raise DpapiError("SmartEdu token encryption requires Windows DPAPI")
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    SMARTEDU_TOKEN_PATH.write_bytes(protect_smartedu_token(token))


def clear_smartedu_token() -> None:
    """Remove saved SmartEdu token."""
    if SMARTEDU_TOKEN_PATH.is_file():
        SMARTEDU_TOKEN_PATH.unlink()


def nd_auth_header(access_token: str) -> str:
    """Build X-ND-AUTH header value (tchMaterial-parser shape)."""
    token = access_token.strip()
    if not token:
        return ""
    return f'MAC id="{token}",nonce="0",mac="0"'


def append_access_token(url: str, access_token: str) -> str:
    """Append ?accessToken= when not already present."""
    token = access_token.strip()
    if not token:
        return url
    if "accessToken=" in url:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}accessToken={token}"
