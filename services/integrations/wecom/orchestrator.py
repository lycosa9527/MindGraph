"""Orchestrate WeCom delivery across profile channels."""

from __future__ import annotations

import asyncio

from services.integrations.wecom.app_message_client import send_app_message
from services.integrations.wecom.config import load_wecom_corp_config, load_wecom_profile
from services.integrations.wecom.profiles import WeComNotifyProfile
from services.integrations.wecom.types import WeComChannelResult, WeComMessage, WeComNotifyResult
from services.integrations.wecom.webhook_client import send_webhook


def _profile_enabled_for_delivery(profile: WeComNotifyProfile) -> bool:
    """Return True when profile has at least one deliverable channel."""
    if profile.webhook_enabled:
        return True
    if not profile.app_message_enabled:
        return False
    corp = load_wecom_corp_config()
    return corp.is_complete


async def notify(profile_id: str, message: WeComMessage) -> WeComNotifyResult:
    """Deliver message via all enabled channels for profile_id."""
    profile = load_wecom_profile(profile_id)
    if not _profile_enabled_for_delivery(profile):
        return WeComNotifyResult(profile_id=profile_id, ok=False, not_configured=True)

    tasks: list[asyncio.Task[WeComChannelResult]] = []

    if profile.webhook_enabled:
        tasks.append(asyncio.create_task(send_webhook(profile, message)))
    if profile.app_message_enabled:
        corp = load_wecom_corp_config()
        if corp.is_complete:
            tasks.append(asyncio.create_task(send_app_message(profile, message, corp)))

    if not tasks:
        return WeComNotifyResult(profile_id=profile_id, ok=False, not_configured=True)

    channels = list(await asyncio.gather(*tasks))
    ok = any(channel.ok for channel in channels)
    return WeComNotifyResult(profile_id=profile_id, ok=ok, channels=channels)
