"""Load WeCom integration settings from environment variables."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from services.integrations.wecom.profiles import (
    BUILTIN_PROFILE_IDS,
    PROFILE_ENV_SUFFIX,
    WeComNotifyProfile,
)
from services.integrations.wecom.webhook_constants import (
    WECOM_API_HOST,
    WECOM_WEBHOOK_SEND_PATH,
    WECOM_WEBHOOK_UPLOAD_MEDIA_PATH,
)

logger = logging.getLogger(__name__)

WECOM_WEBHOOK_HOST = WECOM_API_HOST
WECOM_WEBHOOK_PATH = WECOM_WEBHOOK_SEND_PATH


@dataclass(frozen=True)
class WeComCorpConfig:
    """Shared corp app credentials for message/send."""

    corp_id: str
    agent_id: int
    agent_secret: str

    @property
    def is_complete(self) -> bool:
        """True when corp id, agent id, and secret are all set."""
        return bool(self.corp_id and self.agent_secret and self.agent_id > 0)


def _split_userids(raw: str) -> tuple[str, ...]:
    """Parse comma-separated WeCom userids from env."""
    parts = [part.strip() for part in raw.split(",")]
    return tuple(part for part in parts if part)


def validate_wecom_webhook_url(url: str) -> str | None:
    """Return normalized URL or None if host/path/key validation fails."""
    cleaned = url.strip()
    if not cleaned:
        return None
    parsed = urlparse(cleaned)
    if parsed.scheme != "https":
        return None
    if parsed.netloc != WECOM_WEBHOOK_HOST:
        return None
    if parsed.path != WECOM_WEBHOOK_PATH:
        return None
    query = parse_qs(parsed.query)
    key_values = query.get("key", [])
    if not key_values or not key_values[0].strip():
        return None
    return cleaned


def extract_webhook_key(webhook_url: str) -> str | None:
    """Extract key query param from a validated webhook URL."""
    validated = validate_wecom_webhook_url(webhook_url)
    if validated is None:
        return None
    query = parse_qs(urlparse(validated).query)
    key_values = query.get("key", [])
    if not key_values or not key_values[0].strip():
        return None
    return key_values[0].strip()


def build_webhook_upload_media_url(webhook_url: str, media_type: str) -> str | None:
    """Build upload_media URL for file/voice (99110 §文件上传接口)."""
    key = extract_webhook_key(webhook_url)
    if key is None:
        return None
    cleaned_type = media_type.strip().lower()
    if cleaned_type not in {"file", "voice"}:
        return None
    return f"https://{WECOM_WEBHOOK_HOST}{WECOM_WEBHOOK_UPLOAD_MEDIA_PATH}?key={key}&type={cleaned_type}"


def load_wecom_corp_config() -> WeComCorpConfig:
    """Load shared corp app credentials."""
    corp_id = os.getenv("WECOM_CORP_ID", "").strip()
    agent_secret = os.getenv("WECOM_AGENT_SECRET", "").strip()
    agent_raw = os.getenv("WECOM_AGENT_ID", "").strip()
    agent_id = 0
    if agent_raw:
        try:
            agent_id = int(agent_raw)
        except ValueError:
            logger.warning("[WeCom] WECOM_AGENT_ID is not a valid integer")
    return WeComCorpConfig(corp_id=corp_id, agent_id=agent_id, agent_secret=agent_secret)


def load_wecom_profile(profile_id: str) -> WeComNotifyProfile:
    """Load one profile from WECOM_PROFILE_{SUFFIX}_* env vars."""
    suffix = PROFILE_ENV_SUFFIX.get(profile_id)
    if suffix is None:
        return WeComNotifyProfile(profile_id=profile_id)

    prefix = f"WECOM_PROFILE_{suffix}"
    webhook_raw = os.getenv(f"{prefix}_WEBHOOK_URL", "").strip()
    webhook_url = validate_wecom_webhook_url(webhook_raw) if webhook_raw else None
    if webhook_raw and webhook_url is None:
        logger.warning("[WeCom] Invalid webhook URL for profile %s (host/path/key check failed)", profile_id)

    mention_raw = os.getenv(f"{prefix}_WEBHOOK_MENTION_USERIDS", "").strip()
    mention_mobile_raw = os.getenv(f"{prefix}_WEBHOOK_MENTION_MOBILE_LIST", "").strip()
    notify_raw = os.getenv(f"{prefix}_NOTIFY_USERIDS", "").strip()
    return WeComNotifyProfile(
        profile_id=profile_id,
        webhook_url=webhook_url,
        webhook_mention_userids=_split_userids(mention_raw),
        webhook_mention_mobile_list=_split_userids(mention_mobile_raw),
        notify_userids=_split_userids(notify_raw),
    )


def load_all_wecom_profiles() -> dict[str, WeComNotifyProfile]:
    """Load all built-in profiles."""
    return {profile_id: load_wecom_profile(profile_id) for profile_id in BUILTIN_PROFILE_IDS}
