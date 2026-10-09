"""Bayi mode keeps open sign-up on a mobile number plus a school invitation code."""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from models.requests.requests_auth import RegisterRequest
from utils.auth import registration_gate
from utils.invitations import generate_invitation_code, invitation_code_is_valid, normalize_invitation_code


def test_bayi_blocks_email_signup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Email registration has no school, so bayi mode refuses it."""
    monkeypatch.setattr(registration_gate.auth_configuration, "AUTH_MODE", "bayi")
    with pytest.raises(HTTPException) as caught:
        registration_gate.http_forbid_email_signup_in_bayi("en")
    assert caught.value.status_code == 403
    assert "invitation code" in str(caught.value.detail).lower()


def test_standard_mode_allows_email_signup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Other modes still use the overseas email path."""
    monkeypatch.setattr(registration_gate.auth_configuration, "AUTH_MODE", "standard")
    registration_gate.http_forbid_email_signup_in_bayi("zh")


def test_generated_invitation_code_can_be_used_to_register() -> None:
    """A freshly minted school code matches the public signup format."""
    minted = generate_invitation_code()
    assert invitation_code_is_valid(minted)
    assert not invitation_code_is_valid("BAYI2024")


def test_invitation_code_normalizes_spaces_and_dashes() -> None:
    """Pasted codes with spaces or a lookalike dash still match XXX-XXX."""
    assert normalize_invitation_code("  abc – 234 ") == "ABC-234"
    assert normalize_invitation_code("wxyz-ab c12") == "WXYZ-ABC12"


def test_register_request_keeps_name_and_phone_fields() -> None:
    """The form posts name and phone; spaces and a country code are normalized."""
    body = RegisterRequest(
        phone="86 138 1234 5678",
        password="Teacher-pass-99",
        name="  张伟  ",
        invitation_code="abc-234",
        captcha="AB3D",
        captcha_id="uuid-captcha-session",
    )
    assert body.phone == "13812345678"
    assert body.name == "张伟"


def test_register_request_rejects_a_name_that_is_a_phone_number() -> None:
    """A phone number pasted into the name box is not stored as the display name."""
    with pytest.raises(ValidationError):
        RegisterRequest(
            phone="13812345678",
            password="Teacher-pass-99",
            name="13812345678",
            invitation_code="abc-234",
            captcha="AB3D",
            captcha_id="uuid-captcha-session",
        )
