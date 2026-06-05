"""Overseas registration academic-email feature flag (SWOT_ACADEMIC_EMAIL_REQUIRED)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app
from services.auth import swot_academic
from utils.auth.overseas_registration_messages import (
    overseas_education_email_required,
    overseas_registration_error,
    overseas_registration_message_key,
)
from utils.email_mainland_china import raise_if_mainland_china_email_for_overseas_registration


def test_is_academic_email_required_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SWOT_ACADEMIC_EMAIL_REQUIRED", raising=False)
    assert swot_academic.is_academic_email_required_for_purpose("register") is False
    assert swot_academic.is_academic_email_required_for_purpose("login") is False


def test_is_academic_email_required_on_for_register(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SWOT_ACADEMIC_EMAIL_REQUIRED", "true")
    assert swot_academic.is_academic_email_required_for_purpose("register") is True
    assert swot_academic.is_academic_email_required_for_purpose("login") is False


def test_require_academic_skips_gmail_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SWOT_ACADEMIC_EMAIL_REQUIRED", raising=False)
    swot_academic.require_academic_email_if_configured("user@gmail.com", "register", "en")


def test_require_academic_rejects_gmail_when_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SWOT_ACADEMIC_EMAIL_REQUIRED", "true")
    with pytest.raises(HTTPException) as exc:
        swot_academic.require_academic_email_if_configured("user@gmail.com", "register", "en")
    assert exc.value.status_code == 400


def test_mainland_china_domain_blocked_when_academic_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SWOT_ACADEMIC_EMAIL_REQUIRED", raising=False)
    with pytest.raises(HTTPException) as exc:
        raise_if_mainland_china_email_for_overseas_registration("user@qq.com", "en")
    assert exc.value.status_code == 400
    assert "school email" not in str(exc.value.detail).lower()


@pytest.mark.parametrize("flag_value", [False, True])
def test_auth_mode_exposes_overseas_education_flag(
    monkeypatch: pytest.MonkeyPatch,
    flag_value: bool,
) -> None:
    monkeypatch.setenv("SWOT_ACADEMIC_EMAIL_REQUIRED", "true" if flag_value else "false")
    client = TestClient(app)
    response = client.get("/api/auth/mode")
    assert response.status_code == 200
    payload = response.json()
    assert payload["overseas_education_email_required"] is flag_value


@pytest.mark.parametrize(
    "base_key,flag_on,expected_suffix",
    [
        ("registration_email_not_available_in_region", False, "_any"),
        ("registration_email_not_available_in_region", True, ""),
        ("registration_email_mainland_china_domain", False, "_any"),
        ("register_overseas_acknowledgment_required", False, "_any"),
    ],
)
def test_overseas_registration_message_key(
    monkeypatch: pytest.MonkeyPatch,
    base_key: str,
    flag_on: bool,
    expected_suffix: str,
) -> None:
    monkeypatch.setenv("SWOT_ACADEMIC_EMAIL_REQUIRED", "true" if flag_on else "false")
    assert overseas_registration_message_key(base_key) == f"{base_key}{expected_suffix}"


def test_overseas_registration_error_uses_generic_copy_when_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SWOT_ACADEMIC_EMAIL_REQUIRED", raising=False)
    msg = overseas_registration_error("registration_email_not_available_in_region", "en")
    assert "Education email" not in msg
    assert "Email registration" in msg


def test_overseas_education_email_required_reads_env_each_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SWOT_ACADEMIC_EMAIL_REQUIRED", "false")
    assert overseas_education_email_required() is False
    monkeypatch.setenv("SWOT_ACADEMIC_EMAIL_REQUIRED", "true")
    assert overseas_education_email_required() is True
