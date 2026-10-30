"""Phone and token calls, matching the Chrome extension verify step."""

from __future__ import annotations

import json
import uuid
import urllib.error
import urllib.request
from typing import Any

CLIENT = "desktop-pet"
TIMEOUT_SECONDS = 20


class ApiError(Exception):
    """A verify, unread, or update call failed."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def normalize_origin(server: str) -> str:
    """Turn a preset host into an origin with a scheme and no trailing slash."""
    text = server.strip().rstrip("/")
    if text.startswith("http://") or text.startswith("https://"):
        return text
    if text.startswith("localhost") or text.startswith("127.0.0.1"):
        return f"http://{text}"
    return f"https://{text}"


def _headers(phone: str, token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token.strip()}",
        "X-MG-Account": phone.strip(),
        "X-MG-Client": CLIENT,
        "X-Request-Id": uuid.uuid4().hex,
    }


def _get(url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return int(response.status), response.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ApiError("network") from exc


def verify(server: str, phone: str, token: str) -> None:
    """GET /api/auth/me. Raises ApiError when the phone and token are refused."""
    if not server.strip() or not phone.strip() or not token.strip():
        raise ApiError("incomplete")
    status, _body = _get(f"{normalize_origin(server)}/api/auth/me", _headers(phone, token))
    if status in {401, 403}:
        raise ApiError("rejected")
    if status != 200:
        raise ApiError("server")


def unread_summary(server: str, phone: str, token: str) -> dict[str, Any]:
    """Live seminar unread counts. A 404 means the feature is off, so the badge stays clear."""
    status, body = _get(
        f"{normalize_origin(server)}/api/mindmate/seminar/unread-summary",
        _headers(phone, token),
    )
    if status == 404:
        return {"unread_count": 0, "rooms": []}
    if status in {401, 403}:
        raise ApiError("rejected")
    if status != 200:
        raise ApiError("server")
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ApiError("server") from exc
    if not isinstance(parsed, dict):
        raise ApiError("server")
    return parsed


def update_offer(server: str, phone: str, token: str, platform: str) -> dict[str, Any] | None:
    """Newest published build, or None when this server has not published one."""
    status, body = _get(
        f"{normalize_origin(server)}/api/desktop-pet/update?platform={platform}",
        _headers(phone, token),
    )
    if status == 404:
        return None
    if status in {401, 403}:
        raise ApiError("rejected")
    if status != 200:
        raise ApiError("server")
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ApiError("server") from exc
    if not isinstance(parsed, dict) or not parsed.get("url"):
        return None
    return parsed
