"""User-facing DingTalk bind reply messages (zh)."""

from __future__ import annotations

from services.auth.dingtalk_bind_constants import (
    BIND_ERROR_INTERNAL,
    BIND_ERROR_ORG_MISMATCH,
    BIND_ERROR_STAFF_TAKEN,
    BIND_ERROR_TOKEN_CONSUMED,
    BIND_ERROR_TOKEN_EXPIRED,
)
from services.mindbot.errors import MindbotErrorCode

_BIND_MESSAGES: dict[MindbotErrorCode, str] = {
    MindbotErrorCode.BIND_OK: ("绑定成功！您的钉钉已与 MindGraph 账户关联，生成的导图将保存到您的图库。"),
    MindbotErrorCode.BIND_TOKEN_EXPIRED: (
        "绑定二维码已过期或验证码不正确，请在 MindGraph「账户信息 → 绑定账户」重新生成后再发送。"
    ),
    MindbotErrorCode.BIND_TOKEN_CONSUMED: ("该二维码已被使用，请重新生成新的二维码。"),
    MindbotErrorCode.BIND_ORG_MISMATCH: ("此二维码与当前学校钉钉机器人不匹配，请确认在正确的学校机器人中发送。"),
    MindbotErrorCode.BIND_STAFF_TAKEN: (
        "该钉钉账号已绑定其他 MindGraph 账户。如需更换，请先在网页「账户信息」解绑后再试。"
    ),
    MindbotErrorCode.BIND_IMAGE_UNREADABLE: ("无法读取图片，请发送完整的绑定二维码截图（勿裁剪、勿模糊）。"),
    MindbotErrorCode.BIND_UNAVAILABLE: (
        "绑定功能暂不可用（需管理员配置钉钉 OpenAPI 与二维码解码）。请稍后重试或联系管理员。"
    ),
    MindbotErrorCode.BIND_INVALID_STAFF: (
        "无法识别您的钉钉身份，请确认在单聊窗口中发送二维码，或联系管理员检查机器人配置。"
    ),
    MindbotErrorCode.BIND_INTERNAL: ("绑定失败，请稍后重试。如持续失败请联系管理员。"),
}

_CLAIM_ERROR_TO_MINDBOT: dict[str, MindbotErrorCode] = {
    BIND_ERROR_TOKEN_EXPIRED: MindbotErrorCode.BIND_TOKEN_EXPIRED,
    BIND_ERROR_TOKEN_CONSUMED: MindbotErrorCode.BIND_TOKEN_CONSUMED,
    BIND_ERROR_ORG_MISMATCH: MindbotErrorCode.BIND_ORG_MISMATCH,
    BIND_ERROR_STAFF_TAKEN: MindbotErrorCode.BIND_STAFF_TAKEN,
    BIND_ERROR_INTERNAL: MindbotErrorCode.BIND_INTERNAL,
}


def mindbot_code_from_claim_error(error_code: str) -> MindbotErrorCode:
    """Map universal claim ``error_code`` strings to MindBot enum values."""
    return _CLAIM_ERROR_TO_MINDBOT.get(error_code, MindbotErrorCode.BIND_INTERNAL)


def bind_reply_text(code: MindbotErrorCode) -> str:
    """Return short DingTalk reply for a bind outcome code."""
    return _BIND_MESSAGES.get(
        code,
        _BIND_MESSAGES[MindbotErrorCode.BIND_INTERNAL],
    )


def bind_outcome_codes_with_messages() -> frozenset[MindbotErrorCode]:
    """Return MindBot bind codes that have explicit user-facing copy."""
    return frozenset(_BIND_MESSAGES.keys())
