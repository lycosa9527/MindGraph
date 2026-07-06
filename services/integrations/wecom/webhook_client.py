"""WeCom group message push via webhook/send (doc 99110)."""

from __future__ import annotations

from typing import Any

from services.integrations.wecom import webhook_http
from services.integrations.wecom.profiles import WeComNotifyProfile
from services.integrations.wecom.types import WeComChannelResult, WeComMessage


async def send_webhook_payload(
    profile: WeComNotifyProfile,
    payload: dict[str, Any],
) -> WeComChannelResult:
    """POST an arbitrary 99110 webhook payload to the profile URL."""
    if not profile.webhook_enabled or not profile.webhook_url:
        return WeComChannelResult(
            channel="webhook",
            ok=False,
            skipped=True,
            skip_reason="webhook_not_configured",
        )

    body, exc = await webhook_http.post_json_safe(
        profile.webhook_url,
        payload,
        channel="webhook",
        profile_id=profile.profile_id,
    )
    if exc is not None:
        return WeComChannelResult(channel="webhook", ok=False, errmsg=str(exc))
    if body is None:
        return WeComChannelResult(channel="webhook", ok=False, errmsg="empty response")

    errcode_raw = body.get("errcode")
    errmsg_raw = body.get("errmsg")
    errcode: int | None = None
    if errcode_raw is not None:
        try:
            errcode = int(errcode_raw)
        except (TypeError, ValueError):
            errcode = None
    ok = errcode == 0
    errmsg = str(errmsg_raw) if errmsg_raw is not None else None
    return WeComChannelResult(channel="webhook", ok=ok, errcode=errcode, errmsg=errmsg)


async def send_webhook(profile: WeComNotifyProfile, message: WeComMessage) -> WeComChannelResult:
    """Send structured WeComMessage as markdown with optional @ mentions."""
    payload = message.build_webhook_markdown_payload(profile.webhook_mention_userids)
    return await send_webhook_payload(profile, payload)
