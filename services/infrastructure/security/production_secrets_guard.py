"""
Production startup guards for authentication secrets and dangerous auth modes.

Fails fast in non-debug deployments when weak defaults or missing required secrets
would expose the application.
"""

from __future__ import annotations

import logging
import os

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
