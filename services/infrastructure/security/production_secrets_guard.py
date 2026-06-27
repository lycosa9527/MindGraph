"""
Production startup guards for authentication secrets and dangerous auth modes.

Fails fast in non-debug deployments when weak defaults or missing required secrets
would expose the application.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

from config.settings import config
from utils.auth.config import (
    AUTH_MODE,
    BAYI_DECRYPTION_KEY,
    BAYI_PASSKEY,
    PUBLIC_DASHBOARD_PASSKEY,
)

logger = logging.getLogger(__name__)

_KNOWN_WEAK_PASSKEYS = frozenset({"888888", "123456", "000000", "111111"})
_KNOWN_WEAK_DASHBOARD_PASSKEYS = frozenset({"123456", "000000", "888888"})
_KNOWN_WEAK_BAYI_KEYS = frozenset({"v8IT7XujLPsM7FYuDPRhPtZk"})
_PLACEHOLDER_SUBSTRINGS = ("change-me", "changeme", "replace-me", "example", "placeholder")
_ENTERPRISE_ACK = "I_UNDERSTAND_PUBLIC_EXPOSURE_RISK"


def _env_truthy(name: str) -> bool:
    """True when an env flag is set to a truthy value."""
    return os.getenv(name, "").strip().lower() in ("true", "1", "yes")


def _guard_database_url() -> None:
    """Block startup when DATABASE_URL is unset in non-debug deployments."""
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        _fail("DATABASE_URL must be set explicitly in production (no insecure default)")


def _guard_redis_url() -> None:
    """Warn (or fail when REQUIRE_REDIS_AUTH=true) on an unauthenticated REDIS_URL."""
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return
    try:
        parsed = urlparse(redis_url)
    except ValueError:
        return
    has_auth = bool(parsed.password)
    uses_tls = parsed.scheme == "rediss"
    if has_auth or uses_tls:
        return
    if _env_truthy("REQUIRE_REDIS_AUTH"):
        _fail("REDIS_URL has no password/TLS and REQUIRE_REDIS_AUTH=true — configure authentication")
    logger.warning(
        "[SECURITY] REDIS_URL appears unauthenticated (no password/TLS). "
        "Ensure Redis is network-isolated, or set a password and REQUIRE_REDIS_AUTH=true."
    )


def _is_placeholder_secret(value: str) -> bool:
    """True when a secret looks like an env.example placeholder, not production-ready."""
    lowered = value.strip().lower()
    if not lowered:
        return True
    return any(token in lowered for token in _PLACEHOLDER_SUBSTRINGS)


def _require_strong_secret(name: str, value: str, weak_values: frozenset[str]) -> None:
    if not value or value in weak_values or _is_placeholder_secret(value):
        _fail(f"Set a strong {name} (not empty, weak defaults, or CHANGE-ME placeholders)")


def _require_non_debug() -> bool:
    return not config.debug


def _fail(message: str) -> None:
    logger.critical("[SECURITY] Startup blocked: %s", message)
    raise RuntimeError(message)


def enforce_production_security_guards() -> None:
    """Raise RuntimeError when production configuration is unsafe."""
    if not _require_non_debug():
        return

    _guard_database_url()
    _guard_redis_url()

    if AUTH_MODE == "enterprise":
        ack = os.getenv("ENTERPRISE_MODE_PUBLIC_ACK", "").strip()
        if ack != _ENTERPRISE_ACK:
            _fail(
                f"AUTH_MODE=enterprise requires ENTERPRISE_MODE_PUBLIC_ACK={_ENTERPRISE_ACK} in non-debug deployments"
            )

    if AUTH_MODE == "bayi":
        _require_strong_secret("BAYI_PASSKEY", BAYI_PASSKEY, _KNOWN_WEAK_PASSKEYS)
        _require_strong_secret("BAYI_DECRYPTION_KEY", BAYI_DECRYPTION_KEY, _KNOWN_WEAK_BAYI_KEYS)

    if PUBLIC_DASHBOARD_PASSKEY:
        _require_strong_secret(
            "PUBLIC_DASHBOARD_PASSKEY",
            PUBLIC_DASHBOARD_PASSKEY,
            _KNOWN_WEAK_DASHBOARD_PASSKEYS,
        )

    device_secret = os.getenv("DEVICE_REGISTRATION_SECRET", "").strip()
    if os.getenv("FEATURE_SMART_RESPONSE", "False").strip().lower() in ("true", "1", "yes"):
        if not device_secret:
            _fail("DEVICE_REGISTRATION_SECRET is required when FEATURE_SMART_RESPONSE=True")

    gewe_secret = os.getenv("GEWE_WEBHOOK_SECRET", "").strip()
    if os.getenv("FEATURE_GEWE", "False").strip().lower() in ("true", "1", "yes"):
        if not gewe_secret:
            _fail("GEWE_WEBHOOK_SECRET is required when FEATURE_GEWE=True")

    if os.getenv("FEATURE_OAUTH_LOGIN", "False").strip().lower() in ("true", "1", "yes"):
        wechat_id = os.getenv("WECHAT_OAUTH_APP_ID", "").strip()
        wechat_secret = os.getenv("WECHAT_OAUTH_APP_SECRET", "").strip()
        if not wechat_id or not wechat_secret:
            _fail("WECHAT_OAUTH_APP_ID and WECHAT_OAUTH_APP_SECRET are required when FEATURE_OAUTH_LOGIN=True")
        base = os.getenv("EXTERNAL_BASE_URL", "").strip()
        if not base:
            logger.warning("FEATURE_OAUTH_LOGIN=True but EXTERNAL_BASE_URL is unset; OAuth redirect URIs may fail")
