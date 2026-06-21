"""Environment configuration for error collection alerts and retention."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_flag(name: str, default: str) -> bool:
    """Parse a boolean environment variable."""
    return os.getenv(name, default).lower() in ("true", "1", "yes")


def error_collection_enabled() -> bool:
    """Whether error events are persisted."""
    return _env_flag("ERROR_COLLECTION_ENABLED", "true")


def error_alerts_enabled() -> bool:
    """Whether non-SMS error alerts may fire."""
    if os.getenv("DEBUG", "").lower() == "true":
        return False
    return _env_flag("ERROR_ALERT_ENABLED", "true")


def error_alert_threshold() -> int:
    """Minimum occurrences within the alert window before threshold alerts fire."""
    raw = os.getenv("ERROR_ALERT_THRESHOLD_COUNT", "5")
    try:
        return max(1, int(raw))
    except ValueError:
        return 5


def error_alert_window_seconds() -> int:
    """Sliding window length for threshold-based alerts."""
    raw = os.getenv("ERROR_ALERT_THRESHOLD_WINDOW_SECONDS", "300")
    try:
        return max(60, int(raw))
    except ValueError:
        return 300


def error_alert_cooldown_seconds() -> int:
    """Cooldown between duplicate alerts for the same fingerprint."""
    raw = os.getenv("ERROR_ALERT_COOLDOWN_SECONDS", "1800")
    try:
        return max(60, int(raw))
    except ValueError:
        return 1800


def error_retention_days() -> int:
    """Number of days to retain raw error_events rows."""
    raw = os.getenv("ERROR_RETENTION_DAYS", "90")
    try:
        return max(1, int(raw))
    except ValueError:
        return 90


@dataclass
class ErrorAlertConfig:
    """Runtime alert channel configuration (from environment)."""

    enabled: bool
    webhook_url: str | None
    dingtalk_webhook_url: str | None
    threshold_count: int
    threshold_window_seconds: int
    cooldown_seconds: int


def get_error_alert_config() -> ErrorAlertConfig:
    """Load alert channel settings from environment variables."""
    webhook = os.getenv("ERROR_ALERT_WEBHOOK_URL", "").strip() or None
    dingtalk = os.getenv("ERROR_ALERT_DINGTALK_WEBHOOK_URL", "").strip() or None
    return ErrorAlertConfig(
        enabled=error_alerts_enabled(),
        webhook_url=webhook,
        dingtalk_webhook_url=dingtalk,
        threshold_count=error_alert_threshold(),
        threshold_window_seconds=error_alert_window_seconds(),
        cooldown_seconds=error_alert_cooldown_seconds(),
    )
