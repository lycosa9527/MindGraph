"""Tests for MindBot bind user messages."""

from services.auth.dingtalk_bind_constants import (
    BIND_ERROR_INTERNAL,
    BIND_ERROR_ORG_MISMATCH,
    BIND_ERROR_STAFF_TAKEN,
    BIND_ERROR_TOKEN_CONSUMED,
    BIND_ERROR_TOKEN_EXPIRED,
)
from services.mindbot.bind.messages import (
    bind_outcome_codes_with_messages,
    bind_reply_text,
    mindbot_code_from_claim_error,
)
from services.mindbot.errors import MindbotErrorCode


def test_bind_reply_contains_actionable_text() -> None:
    """Bind reply messages include user-facing success and expiry text."""
    expired = bind_reply_text(MindbotErrorCode.BIND_TOKEN_EXPIRED)
    assert "过期" in expired or "過期" in expired or "expired" in expired.lower()

    ok = bind_reply_text(MindbotErrorCode.BIND_OK)
    assert "绑定成功" in ok or "成功" in ok


def test_every_bind_outcome_has_user_message() -> None:
    """Each MindBot bind outcome enum used in ingress has non-empty zh copy."""
    expected = {
        MindbotErrorCode.BIND_OK,
        MindbotErrorCode.BIND_TOKEN_EXPIRED,
        MindbotErrorCode.BIND_TOKEN_CONSUMED,
        MindbotErrorCode.BIND_ORG_MISMATCH,
        MindbotErrorCode.BIND_STAFF_TAKEN,
        MindbotErrorCode.BIND_IMAGE_UNREADABLE,
        MindbotErrorCode.BIND_UNAVAILABLE,
        MindbotErrorCode.BIND_INVALID_STAFF,
        MindbotErrorCode.BIND_INTERNAL,
    }
    assert bind_outcome_codes_with_messages() == expected
    for code in expected:
        text = bind_reply_text(code)
        assert isinstance(text, str)
        assert len(text.strip()) >= 8


def test_claim_error_mapping_covers_all_constants() -> None:
    """Universal claim error strings map to MindBot bind codes."""
    assert mindbot_code_from_claim_error(BIND_ERROR_TOKEN_EXPIRED) == MindbotErrorCode.BIND_TOKEN_EXPIRED
    assert mindbot_code_from_claim_error(BIND_ERROR_TOKEN_CONSUMED) == MindbotErrorCode.BIND_TOKEN_CONSUMED
    assert mindbot_code_from_claim_error(BIND_ERROR_ORG_MISMATCH) == MindbotErrorCode.BIND_ORG_MISMATCH
    assert mindbot_code_from_claim_error(BIND_ERROR_STAFF_TAKEN) == MindbotErrorCode.BIND_STAFF_TAKEN
    assert mindbot_code_from_claim_error(BIND_ERROR_INTERNAL) == MindbotErrorCode.BIND_INTERNAL
    assert mindbot_code_from_claim_error("MINDBOT_BIND_UNKNOWN") == MindbotErrorCode.BIND_INTERNAL
