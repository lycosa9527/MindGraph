"""Same-device refresh must survive overnight header drift."""

from unittest.mock import MagicMock

from services.redis import keys as redis_keys
from utils.auth.config import ACCESS_TOKEN_EXPIRY_MINUTES, REFRESH_TOKEN_EXPIRY_DAYS
from utils.auth.tokens import (
    DEVICE_COOKIE_NAME,
    assign_device_id,
    compute_device_hash,
    device_binding_matches,
)


def _request(headers: dict[str, str], cookies: dict[str, str] | None = None) -> MagicMock:
    """Minimal request stand-in that implements headers.get and cookies.get."""
    request = MagicMock()
    request.headers.get.side_effect = lambda key, default="": headers.get(key, default)
    cookie_map = cookies or {}
    request.cookies.get.side_effect = lambda key, default="": cookie_map.get(key, default)
    return request


def test_device_hash_ignores_encoding_and_client_hints() -> None:
    """Chrome adding zstd or Sec-CH-UA overnight must not look like a new device."""
    morning = _request({"User-Agent": "Mozilla/5.0 Chrome/140"})
    afternoon = _request(
        {
            "User-Agent": "Mozilla/5.0 Chrome/140",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Sec-CH-UA-Platform": '"Windows"',
            "Sec-CH-UA-Mobile": "?0",
        }
    )
    assert compute_device_hash(morning) == compute_device_hash(afternoon)


def test_device_hash_prefers_device_cookie() -> None:
    """The httpOnly device cookie is the binding, not today's request headers."""
    cookie_id = "aa" * 16
    first = _request({"User-Agent": "Chrome/140"}, {DEVICE_COOKIE_NAME: cookie_id})
    second = _request({"User-Agent": "Chrome/141"}, {DEVICE_COOKIE_NAME: cookie_id})
    assert compute_device_hash(first) == cookie_id
    assert compute_device_hash(second) == cookie_id


def test_assign_device_id_reuses_cookie() -> None:
    """A second login in the same browser must keep the same device slot."""
    cookie_id = "bb" * 16
    request = _request({"User-Agent": "Chrome/140"}, {DEVICE_COOKIE_NAME: cookie_id})
    assert assign_device_id(request) == cookie_id


def test_assign_device_id_mints_when_cookie_missing() -> None:
    """First login in a browser gets a unique id, not a shared UA hash."""
    minted = assign_device_id(_request({"User-Agent": "Chrome/140"}))
    assert len(minted) == 32
    assert minted != assign_device_id(_request({"User-Agent": "Chrome/140"}))


def test_device_hash_changes_when_user_agent_changes() -> None:
    """Without a cookie, a different browser must not reuse the previous slot."""
    first = _request({"User-Agent": "Chrome/140"})
    second = _request({"User-Agent": "Firefox/140"})
    assert compute_device_hash(first) != compute_device_hash(second)


def test_device_binding_allows_hash_drift_when_user_agent_matches() -> None:
    """Old fingerprints still refresh when the stored User-Agent is unchanged."""
    same_ua = "Mozilla/5.0 Chrome/140"
    assert device_binding_matches(
        stored_device_hash="oldhash",
        current_device_hash="newhash",
        stored_user_agent=same_ua,
        current_user_agent=same_ua,
    )
    assert not device_binding_matches(
        stored_device_hash="oldhash",
        current_device_hash="newhash",
        stored_user_agent=same_ua,
        current_user_agent="Mozilla/5.0 Firefox/140",
    )


def test_device_binding_accepts_matching_hash() -> None:
    """Matching hashes win even if User-Agent text drifted."""
    assert device_binding_matches("abc", "abc", "Chrome", "Firefox")


def test_refresh_cookie_and_redis_ttl_match() -> None:
    """Browser cookie max-age and Redis key TTL must use the same day count."""
    cookie_seconds = REFRESH_TOKEN_EXPIRY_DAYS * 24 * 60 * 60
    assert cookie_seconds >= 7 * 24 * 60 * 60
    assert redis_keys.TTL_REFRESH_TOKEN == cookie_seconds
    assert redis_keys.TTL_ACCESS_SESSION == ACCESS_TOKEN_EXPIRY_MINUTES * 60
