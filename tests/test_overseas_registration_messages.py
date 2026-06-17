"""Overseas registration user-visible message keys."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from utils.auth.overseas_registration_messages import (
    overseas_registration_error,
    overseas_registration_message_key,
)
from utils.email_mainland_china import raise_if_mainland_china_email_for_overseas_registration


@pytest.mark.parametrize(
    "base_key,expected",
    [
        ("registration_email_not_available_in_region", "registration_email_not_available_in_region_any"),
        ("registration_email_mainland_china_domain", "registration_email_mainland_china_domain_any"),
        ("register_overseas_acknowledgment_required", "register_overseas_acknowledgment_required_any"),
        ("captcha_incorrect", "captcha_incorrect"),
    ],
)
def test_overseas_registration_message_key(base_key: str, expected: str) -> None:
    """Test overseas registration message key."""
    assert overseas_registration_message_key(base_key) == expected


def test_overseas_registration_error_uses_generic_copy() -> None:
    """Test overseas registration error uses generic copy."""
    msg = overseas_registration_error("registration_email_not_available_in_region", "en")
    assert "Education email" not in msg
    assert "Email registration" in msg


def test_mainland_china_domain_blocked_for_overseas_registration() -> None:
    """Test mainland china domain blocked for overseas registration."""
    with pytest.raises(HTTPException) as exc:
        raise_if_mainland_china_email_for_overseas_registration("user@qq.com", "en")
    assert exc.value.status_code == 400
    assert "school email" not in str(exc.value.detail).lower()
