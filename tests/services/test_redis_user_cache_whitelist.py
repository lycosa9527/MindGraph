"""Redis user cache: email_login_whitelisted_from_cn round-trip."""
from __future__ import annotations

from models.domain.auth import User
from services.redis.cache.redis_user_cache import UserCache


def _minimal_user(uid: int) -> User:
    user = User()
    user.id = uid
    user.password_hash = "h"
    user.failed_login_attempts = 0
    user.email_login_whitelisted_from_cn = False
    return user


def test_serialize_deserialize_whitelist_false() -> None:
    cache = UserCache()
    user = _minimal_user(42)
    user.email_login_whitelisted_from_cn = False
    data = cache._serialize_user(user)
    assert data["email_login_whitelisted_from_cn"] == "0"
    out = cache._deserialize_user(data)
    assert out.email_login_whitelisted_from_cn is False


def test_serialize_deserialize_whitelist_true() -> None:
    cache = UserCache()
    user = _minimal_user(43)
    user.email_login_whitelisted_from_cn = True
    data = cache._serialize_user(user)
    assert data["email_login_whitelisted_from_cn"] == "1"
    out = cache._deserialize_user(data)
    assert out.email_login_whitelisted_from_cn is True


def test_deserialize_missing_whitelist_defaults_false() -> None:
    cache = UserCache()
    minimal = {
        "id": "1",
        "phone": "",
        "email": "",
        "password_hash": "x",
        "name": "",
        "organization_id": "",
        "avatar": "",
        "role": "user",
        "failed_login_attempts": "0",
        "locked_until": "",
        "created_at": "",
        "last_login": "",
        "ui_language": "",
        "prompt_language": "",
        "allows_simplified_chinese": "1",
    }
    out = cache._deserialize_user(minimal)
    assert out.email_login_whitelisted_from_cn is False
