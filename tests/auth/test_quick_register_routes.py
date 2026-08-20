"""Unit tests for public quick-registration channel GETs."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from routers.auth import quick_register
from routers.auth.quick_register import quick_register_room_code, quick_register_status


def _request() -> MagicMock:
    """Request with a client IP for rate-limit keys."""
    request = MagicMock()
    request.headers = {}
    request.client = SimpleNamespace(host="203.0.113.10")
    return request


@pytest.fixture(name="_rate_ok")
def fixture_rate_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow every public GET rate-limit check."""
    limiter = MagicMock()
    limiter.check_and_record = AsyncMock(return_value=(True, 1, 60))
    monkeypatch.setattr(quick_register, "get_rate_limiter", lambda: limiter)
    monkeypatch.setattr(quick_register, "get_client_ip", lambda _req: "203.0.113.10")
    monkeypatch.setattr(quick_register, "http_forbid_if_registration_disabled", lambda _lang: None)


@pytest.mark.asyncio
async def test_status_ok_does_not_return_room_code(
    _rate_ok: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Attendee probe only reports that the channel is still open."""
    monkeypatch.setattr(
        quick_register,
        "get_token_data",
        AsyncMock(return_value={"organization_id": 7, "room_code_secret": "s"}),
    )

    body = await quick_register_status(
        _request(),
        channel_token="abcdefghijklmnopqrstuvwxyz012345",
        legacy_token=None,
        lang="en",
    )

    assert body == {"valid": True}
    assert "code" not in body


@pytest.mark.asyncio
async def test_status_invalid_token(
    _rate_ok: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing Redis token is a closed channel."""
    monkeypatch.setattr(quick_register, "get_token_data", AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as exc:
        await quick_register_status(
            _request(),
            channel_token="abcdefghijklmnopqrstuvwxyz012345",
            legacy_token=None,
            lang="en",
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_room_code_still_returns_digits(
    _rate_ok: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Facilitator poll still receives the rotating code."""
    monkeypatch.setattr(
        quick_register,
        "get_token_data",
        AsyncMock(
            return_value={
                "organization_id": 7,
                "channel_type": "workshop",
                "room_code_secret": "secret-material",
            }
        ),
    )
    monkeypatch.setattr(quick_register, "get_workshop_usage_count", AsyncMock(return_value=3))
    monkeypatch.setattr(
        quick_register,
        "current_room_code_from_room_secret",
        lambda _secret, _token: ("123456", 1, 30.0, 10.0),
    )

    body = await quick_register_room_code(
        _request(),
        channel_token="abcdefghijklmnopqrstuvwxyz012345",
        legacy_token=None,
        lang="en",
    )

    assert body["code"] == "123456"
    assert body["signups_count"] == 3


def test_public_get_ip_default_covers_school_nat() -> None:
    """Room-code and status IP caps default to a class-sized NAT burst."""
    assert quick_register.public_get_ip_max("room") >= 600
    assert quick_register.public_get_ip_max("status") >= 600
