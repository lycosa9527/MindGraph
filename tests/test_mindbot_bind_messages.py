"""Tests for MindBot bind user messages."""

from services.mindbot.bind.messages import bind_reply_text
from services.mindbot.errors import MindbotErrorCode


def test_bind_reply_contains_actionable_text() -> None:
    """Bind reply messages include user-facing success and expiry text."""
    expired = bind_reply_text(MindbotErrorCode.BIND_TOKEN_EXPIRED)
    assert "过期" in expired or "過期" in expired or "expired" in expired.lower()

    ok = bind_reply_text(MindbotErrorCode.BIND_OK)
    assert "绑定成功" in ok or "成功" in ok
