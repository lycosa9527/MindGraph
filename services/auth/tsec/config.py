"""Tencent T-Sec captcha env and provider selection.

CAPTCHA_PROVIDER=tsec (default) or legacy. T-Sec is used only when credentials
are present; otherwise the effective provider is legacy so local login still works.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

PROVIDER_TSEC = "tsec"
PROVIDER_LEGACY = "legacy"
_LEGACY_ALIASES = frozenset({PROVIDER_LEGACY, "svg", "old"})


def requested_captcha_provider() -> str:
    """Return the provider named in CAPTCHA_PROVIDER (default tsec)."""
    raw = (os.getenv("CAPTCHA_PROVIDER", PROVIDER_TSEC) or "").strip().lower()
    if raw in _LEGACY_ALIASES:
        return PROVIDER_LEGACY
    return PROVIDER_TSEC


def tencent_captcha_app_id() -> str:
    """Public CaptchaAppId from the Tencent captcha console."""
    return (os.getenv("TENCENT_CAPTCHA_APP_ID", "") or "").strip()


def tencent_captcha_app_secret_key() -> str:
    """Console AppSecretKey. Server only; never send to the client."""
    return (os.getenv("TENCENT_CAPTCHA_APP_SECRET_KEY", "") or "").strip()


def tencent_captcha_secret_id() -> str:
    """CAM SecretId for DescribeCaptchaResult (falls back to SMS keys)."""
    return (os.getenv("TENCENT_CAPTCHA_SECRET_ID", "") or "").strip() or (
        os.getenv("TENCENT_SMS_SECRET_ID", "") or ""
    ).strip()


def tencent_captcha_secret_key() -> str:
    """CAM SecretKey for DescribeCaptchaResult (falls back to SMS keys)."""
    return (os.getenv("TENCENT_CAPTCHA_SECRET_KEY", "") or "").strip() or (
        os.getenv("TENCENT_SMS_SECRET_KEY", "") or ""
    ).strip()


def _optional_int_env(name: str) -> Optional[int]:
    """Parse an optional reserved integer env, or None when unset/invalid."""
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        logger.warning("T-Sec ignoring invalid %s=%r", name, raw)
        return None


def tencent_captcha_business_id() -> Optional[int]:
    """Optional reserved DescribeCaptchaResult BusinessId."""
    return _optional_int_env("TENCENT_CAPTCHA_BUSINESS_ID")


def tencent_captcha_scene_id() -> Optional[int]:
    """Optional reserved DescribeCaptchaResult SceneId."""
    return _optional_int_env("TENCENT_CAPTCHA_SCENE_ID")


def tsec_credentials_ready() -> bool:
    """True when AppId, AppSecretKey, and CAM signing keys are all set."""
    return bool(
        tencent_captcha_app_id()
        and tencent_captcha_app_secret_key()
        and tencent_captcha_secret_id()
        and tencent_captcha_secret_key()
    )


def effective_captcha_provider() -> str:
    """Provider the SPA and exchange endpoint should use right now."""
    if requested_captcha_provider() != PROVIDER_TSEC:
        return PROVIDER_LEGACY
    if not tsec_credentials_ready():
        return PROVIDER_LEGACY
    return PROVIDER_TSEC


def public_captcha_app_id() -> str:
    """AppId for the SPA when T-Sec is the effective provider."""
    if effective_captcha_provider() != PROVIDER_TSEC:
        return ""
    return tencent_captcha_app_id()
