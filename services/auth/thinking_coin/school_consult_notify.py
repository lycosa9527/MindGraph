"""School consultation form → WeCom notification adapter."""

from __future__ import annotations

from models.domain.auth import User
from services.integrations.wecom import PROFILE_SCHOOL_CONSULT, WeComMessage, WeComNotifyResult, notify


def _user_display_name(user: User) -> str:
    for attr in ("display_name", "name", "username", "phone"):
        value = getattr(user, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str(getattr(user, "id", ""))


async def send_school_consult_notification(
    *,
    name: str,
    phone: str,
    organization: str,
    note: str | None,
    user: User,
    org_name: str | None,
) -> WeComNotifyResult:
    """Build and send school consultation lead to the school_consult profile."""
    fields: dict[str, str] = {
        "姓名": name,
        "电话": phone,
        "学校/机构": organization,
        "MindGraph用户ID": str(getattr(user, "id", "")),
        "MindGraph账号": _user_display_name(user),
    }
    if org_name:
        fields["所属组织"] = org_name
    if note and note.strip():
        fields["补充说明"] = note.strip()

    message = WeComMessage(title="学校版咨询预约", fields=fields)
    return await notify(PROFILE_SCHOOL_CONSULT, message)


def map_notify_result_to_http_status(result: WeComNotifyResult) -> tuple[int, str]:
    """Map notify result to HTTP status code and detail string."""
    if result.not_configured:
        return 503, "School consultation notifications are not configured"
    if result.ok:
        return 200, "ok"
    return 502, "Failed to deliver school consultation notification"
