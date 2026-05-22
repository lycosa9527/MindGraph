"""Production startup guards for Kitty cross-worker control plane."""

from __future__ import annotations

import logging
import os

from config.settings import config

logger = logging.getLogger(__name__)


class KittyProductionGuardError(RuntimeError):
    """Raised when required Kitty production settings are missing."""


def _env_truthy(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def validate_kitty_production_guards() -> None:
    """Require control-plane secret when Kitty WS is enabled in production."""
    if not config.FEATURE_KITTY_WS_ENABLED:
        return
    if os.getenv("ENVIRONMENT", "production").strip().lower() != "production":
        return
    if config.debug:
        return

    secret = os.getenv("KITTY_CONTROL_SHARED_SECRET", "").strip()
    if secret:
        return

    message = (
        "KITTY_CONTROL_SHARED_SECRET is required when FEATURE_KITTY_AGENT is enabled "
        "in production (DEBUG=False)."
    )
    logger.critical("[Kitty] %s", message)
    if _env_truthy("KITTY_STRICT_PROD_GUARDS", "1"):
        raise KittyProductionGuardError(message)
