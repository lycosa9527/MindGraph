"""User-facing DingTalk pair (bind/unbind) reply messages (zh)."""

from __future__ import annotations

from services.auth.dingtalk_bind_constants import (
    BIND_ERROR_INTERNAL,
    BIND_ERROR_ORG_MISMATCH,
    BIND_ERROR_STAFF_TAKEN,
    BIND_ERROR_TOKEN_CONSUMED,
    BIND_ERROR_TOKEN_EXPIRED,
    PAIR_PURPOSE_BIND,
    PAIR_PURPOSE_UNBIND,
    PAIR_PURPOSE_UNKNOWN,
)
from services.mindbot.errors import MindbotErrorCode

_BIND_MESSAGES: dict[MindbotErrorCode, str] = {
    MindbotErrorCode.BIND_OK: (
        "绑定成功！您的钉钉已与 MindGraph 账户关联。此后在 MindBot 中生成的导图将自动保存到您的图库。"
    ),
    MindbotErrorCode.BIND_TOKEN_EXPIRED: (
        "验证码无效或已过期。"
        "请打开 MindGraph「账户信息 → 绑定钉钉」，按页面显示的 6 位数字重新发送"
        "（仅发送验证码，例如 123456 或 123-456）。"
    ),
    MindbotErrorCode.BIND_TOKEN_CONSUMED: (
        "该验证码已失效（可能已被使用）。请关闭网页上的配对窗口，重新发起绑定并发送新的验证码。"
    ),
    MindbotErrorCode.BIND_ORG_MISMATCH: (
        "此验证码与当前 MindBot 不匹配。请确认您在本校 MindBot 的单聊窗口中发送验证码。"
    ),
    MindbotErrorCode.BIND_STAFF_TAKEN: (
        "该钉钉账号已绑定其他 MindGraph 用户。如需绑定当前账户，请先在网页「账户信息」解绑，或更换钉钉账号后重试。"
    ),
    MindbotErrorCode.BIND_IMAGE_UNREADABLE: (
        "未能识别验证码。请仅发送 6 位数字（例如 123456 或 123-456），不要附加其他文字。"
    ),
    MindbotErrorCode.BIND_UNAVAILABLE: ("账户配对功能暂不可用，请稍后重试。若持续失败，请联系学校管理员。"),
    MindbotErrorCode.BIND_INVALID_STAFF: (
        "无法确认您的钉钉身份。请在 MindBot 单聊窗口发送验证码（群聊无效），或联系管理员检查机器人配置。"
    ),
    MindbotErrorCode.BIND_INTERNAL: ("绑定未完成，请稍后重试。若多次失败，请联系管理员。"),
    MindbotErrorCode.UNBIND_OK: ("解绑成功！您的钉钉已与 MindGraph 账户解除关联。"),
    MindbotErrorCode.UNBIND_NOT_LINKED: ("当前 MindGraph 账户未绑定钉钉，无需解绑。"),
    MindbotErrorCode.UNBIND_STAFF_MISMATCH: (
        "验证码与当前钉钉账号不符。请使用已绑定的钉钉账号，在 MindBot 单聊中发送网页上的解绑验证码。"
    ),
}

_UNBIND_OVERRIDES: dict[MindbotErrorCode, str] = {
    MindbotErrorCode.BIND_TOKEN_EXPIRED: (
        "解绑验证码无效或已过期。请打开 MindGraph「账户信息」，重新点击「解绑钉钉」，发送页面最新显示的验证码。"
    ),
    MindbotErrorCode.BIND_TOKEN_CONSUMED: ("该解绑验证码已失效。请关闭网页配对窗口，重新发起解绑并发送新的验证码。"),
    MindbotErrorCode.BIND_ORG_MISMATCH: ("此验证码与当前 MindBot 不匹配。请在本校 MindBot 的单聊窗口发送解绑验证码。"),
    MindbotErrorCode.BIND_INVALID_STAFF: (
        "无法确认您的钉钉身份。请使用已绑定的钉钉账号，在 MindBot 单聊中发送解绑验证码。"
    ),
    MindbotErrorCode.BIND_INTERNAL: ("解绑未完成，请稍后重试。若多次失败，请联系管理员。"),
}

_UNKNOWN_PURPOSE_OVERRIDES: dict[MindbotErrorCode, str] = {
    MindbotErrorCode.BIND_TOKEN_EXPIRED: (
        "验证码无效或已过期。"
        "请打开 MindGraph「账户信息」，按绑定或解绑页面显示的 6 位数字重新发送"
        "（仅发送验证码，例如 123456 或 123-456）。"
    ),
    MindbotErrorCode.BIND_INVALID_STAFF: (
        "无法确认您的钉钉身份。请在 MindBot 单聊窗口发送验证码（群聊无效），或联系管理员检查机器人配置。"
    ),
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


def pair_reply_text(code: MindbotErrorCode, purpose: str = PAIR_PURPOSE_BIND) -> str:
    """Return short DingTalk reply for a pair outcome code."""
    if purpose == PAIR_PURPOSE_UNKNOWN and code in _UNKNOWN_PURPOSE_OVERRIDES:
        return _UNKNOWN_PURPOSE_OVERRIDES[code]
    if purpose == PAIR_PURPOSE_UNBIND and code in _UNBIND_OVERRIDES:
        return _UNBIND_OVERRIDES[code]
    return _BIND_MESSAGES.get(
        code,
        _BIND_MESSAGES[MindbotErrorCode.BIND_INTERNAL],
    )


def bind_reply_text(code: MindbotErrorCode) -> str:
    """Backward-compatible alias for bind pair replies."""
    return pair_reply_text(code, PAIR_PURPOSE_BIND)


def bind_outcome_codes_with_messages() -> frozenset[MindbotErrorCode]:
    """Return MindBot pair codes that have explicit user-facing copy."""
    return frozenset(_BIND_MESSAGES.keys())
