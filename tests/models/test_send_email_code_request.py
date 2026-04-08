"""SendEmailCodeRequest purpose whitelist."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.requests.requests_auth import SendEmailCodeRequest, VerifyEmailCodeRequest


def test_send_email_accepts_register_and_reset_password() -> None:
    req = SendEmailCodeRequest(
        email="a@b.edu",
        purpose="register",
        captcha="ABCD",
        captcha_id="cid",
    )
    assert req.purpose == "register"


def test_send_email_rejects_login_purpose() -> None:
    with pytest.raises(ValidationError):
        SendEmailCodeRequest(
            email="a@b.edu",
            purpose="login",
            captcha="ABCD",
            captcha_id="cid",
        )


def test_verify_email_rejects_change_email_purpose() -> None:
    with pytest.raises(ValidationError):
        VerifyEmailCodeRequest(
            email="a@b.edu",
            code="123456",
            purpose="change_email",
        )
