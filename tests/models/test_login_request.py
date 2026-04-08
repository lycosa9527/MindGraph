"""Tests for LoginRequest identifier validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.requests.requests_auth import LoginRequest


def test_login_accepts_phone_only() -> None:
    req = LoginRequest(
        phone="13800000000",
        password="Secret123!",
        captcha="AB3D",
        captcha_id="captcha-session",
    )
    assert req.phone == "13800000000"
    assert req.email is None


def test_login_accepts_email_only() -> None:
    req = LoginRequest(
        email="student@university.edu",
        password="Secret123!",
        captcha="AB3D",
        captcha_id="captcha-session",
    )
    assert req.email == "student@university.edu"
    assert req.phone is None


def test_login_rejects_both_phone_and_email() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(
            phone="13800000000",
            email="a@b.edu",
            password="Secret123!",
            captcha="AB3D",
            captcha_id="captcha-session",
        )


def test_login_rejects_neither_phone_nor_email() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(
            password="Secret123!",
            captcha="AB3D",
            captcha_id="captcha-session",
        )
