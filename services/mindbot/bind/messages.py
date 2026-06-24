"""User-facing DingTalk bind reply messages (zh)."""

from __future__ import annotations

from services.mindbot.errors import MindbotErrorCode

_BIND_MESSAGES: dict[MindbotErrorCode, str] = {
    MindbotErrorCode.BIND_OK: ("绑定成功！您的钉钉已与 MindGraph 账户关联，生成的导图将保存到您的图库。"),
    MindbotErrorCode.BIND_TOKEN_EXPIRED: ("绑定二维码已过期，请在 MindGraph「账户信息 → 绑定账户」重新生成后再发送。"),
    MindbotErrorCode.BIND_TOKEN_CONSUMED: ("该二维码已被使用，请重新生成新的二维码。"),
    MindbotErrorCode.BIND_ORG_MISMATCH: ("此二维码与当前学校钉钉机器人不匹配，请确认在正确的学校机器人中发送。"),
    MindbotErrorCode.BIND_STAFF_TAKEN: (
        "该钉钉账号已绑定其他 MindGraph 账户。如需更换，请先在网页「账户信息」解绑后再试。"
    ),
    MindbotErrorCode.BIND_IMAGE_UNREADABLE: ("无法读取图片，请发送完整的绑定二维码截图（勿裁剪、勿模糊）。"),
    MindbotErrorCode.BIND_INTERNAL: ("绑定失败，请稍后重试。如持续失败请联系管理员。"),
}


def bind_reply_text(code: MindbotErrorCode) -> str:
    """Return short DingTalk reply for a bind outcome code."""
    return _BIND_MESSAGES.get(
        code,
        _BIND_MESSAGES[MindbotErrorCode.BIND_INTERNAL],
    )
