"""Production startup guards for Kitty cross-worker control plane."""

from __future__ import annotations

import logging
import os

from config.settings import config
from services.kitty.infra.control.kitty_control_secret import get_kitty_control_shared_secret

logger = logging.getLogger(__name__)


class KittyProductionGuardError(RuntimeError):
    """Raised when required Kitty production settings are missing."""


def _env_truthy(name: str, default: str = "0") -> bool:
    """Env truthy."""
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def validate_kitty_production_guards() -> None:
    """Require a warmed control-plane secret when Kitty WS is enabled in production."""
    if not config.FEATURE_KITTY_WS_ENABLED:
        return
    if os.getenv("ENVIRONMENT", "production").strip().lower() != "production":
        return
    if config.debug:
        return

    secret = get_kitty_control_shared_secret()
    if secret:
        return

    message = (
        "Kitty control shared secret is required when FEATURE_KITTY_AGENT is enabled "
        "in production (DEBUG=False). Redis warmup should auto-generate one."
    )
    logger.critical("[Kitty] %s", message)
    if _env_truthy("KITTY_STRICT_PROD_GUARDS", "1"):
        raise KittyProductionGuardError(message)
