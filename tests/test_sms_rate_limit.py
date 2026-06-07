"""SMS notification rate-limit detection."""

from __future__ import annotations

from services.auth.sms_service import (
    SMS_NOTIFICATION_RATE_LIMIT_MESSAGE,
    _is_sms_provider_rate_limit,
)


def test_rate_limit_message_constant_is_stable_for_lifespan() -> None:
    assert SMS_NOTIFICATION_RATE_LIMIT_MESSAGE == "SMS notification blocked by provider rate limit"


def test_is_sms_provider_rate_limit_detects_duplicate_content_message() -> None:
    message = "the number of the same sms messages sent from a single mobile number exceeds the upper limit"
    assert _is_sms_provider_rate_limit("FailedOperation", message) is True


def test_is_sms_provider_rate_limit_detects_limit_exceeded_code() -> None:
    assert _is_sms_provider_rate_limit("LimitExceeded.PhoneNumberSameContentDailyLimit", "x") is True


def test_is_sms_provider_rate_limit_false_for_config_errors() -> None:
    assert _is_sms_provider_rate_limit("FailedOperation.TemplateIncorrectOrUnapproved", "bad template") is False
