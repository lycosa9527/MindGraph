"""Tests for universal DingTalk QR bind claim service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from repositories.dingtalk_staff_link_repo import StaffLinkClaimResult
from services.auth.dingtalk_bind_constants import (
    BIND_ERROR_ORG_MISMATCH,
    BIND_ERROR_STAFF_TAKEN,
    BIND_ERROR_TOKEN_CONSUMED,
)
from services.auth.dingtalk_bind_service import claim_dingtalk_qr_bind
from services.auth.quick_register_room_code import current_room_code_from_room_secret


def _valid_bind_code(secret: str, token: str) -> str:
    code, _, _, _ = current_room_code_from_room_secret(secret, token)
    return code


@pytest.mark.asyncio
async def test_org_mismatch_does_not_consume_token() -> None:
    """Recoverable org mismatch must not burn the Redis bind token."""
    token = "test-bind-token-abc"
    secret = "per-token-secret-material"
    bind_code = _valid_bind_code(secret, token)
    payload = {
        "user_id": 42,
        "organization_id": 5,
        "bind_code_secret": secret,
    }

    with (
        patch(
            "services.auth.dingtalk_bind_service.get_bind_token_consumed",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "services.auth.dingtalk_bind_service.get_bind_token_data",
            new_callable=AsyncMock,
            return_value=payload,
        ),
        patch(
            "services.auth.dingtalk_bind_service.is_bind_code_guess_blocked",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "services.auth.dingtalk_bind_service.consume_bind_token",
            new_callable=AsyncMock,
        ) as mock_consume,
    ):
        ok, err = await claim_dingtalk_qr_bind(
            token=token,
            bind_code=bind_code,
            organization_id=99,
            dingtalk_staff_id="staffA",
        )

    assert ok is False
    assert err == BIND_ERROR_ORG_MISMATCH
    mock_consume.assert_not_called()


@pytest.mark.asyncio
async def test_staff_taken_precheck_does_not_consume_token() -> None:
    """Staff already linked to another user is rejected before consume."""
    token = "test-bind-token-def"
    secret = "another-secret-material"
    bind_code = _valid_bind_code(secret, token)
    payload = {
        "user_id": 42,
        "organization_id": 5,
        "bind_code_secret": secret,
    }
    taken_row = MagicMock()
    taken_row.user_id = 99

    mock_db = AsyncMock()
    mock_repo = MagicMock()
    mock_repo.get_by_staff = AsyncMock(return_value=taken_row)
    mock_repo.claim_staff_link = AsyncMock()

    with (
        patch(
            "services.auth.dingtalk_bind_service.try_acquire_pair_claim_lock",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "services.auth.dingtalk_bind_service.release_pair_claim_lock",
            new_callable=AsyncMock,
        ),
        patch(
            "services.auth.dingtalk_bind_service.get_bind_token_consumed",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "services.auth.dingtalk_bind_service.get_bind_token_data",
            new_callable=AsyncMock,
            return_value=payload,
        ),
        patch(
            "services.auth.dingtalk_bind_service.is_bind_code_guess_blocked",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "services.auth.dingtalk_bind_service.rls_async_session",
        ) as mock_rls,
        patch(
            "services.auth.dingtalk_bind_service.DingtalkStaffLinkRepository",
            return_value=mock_repo,
        ),
        patch(
            "services.auth.dingtalk_bind_service.consume_bind_token",
            new_callable=AsyncMock,
        ) as mock_consume,
    ):
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_rls.return_value = mock_cm

        ok, err = await claim_dingtalk_qr_bind(
            token=token,
            bind_code=bind_code,
            organization_id=5,
            dingtalk_staff_id="staffA",
        )

    assert ok is False
    assert err == BIND_ERROR_STAFF_TAKEN
    mock_consume.assert_not_called()
    mock_repo.claim_staff_link.assert_not_called()


@pytest.mark.asyncio
async def test_success_consumes_after_commit() -> None:
    """Token is consumed only after DB commit succeeds."""
    token = "test-bind-token-ghi"
    secret = "success-secret-material"
    bind_code = _valid_bind_code(secret, token)
    payload = {
        "user_id": 42,
        "organization_id": 5,
        "bind_code_secret": secret,
    }

    mock_db = AsyncMock()
    mock_repo = MagicMock()
    mock_repo.get_by_staff = AsyncMock(return_value=None)
    mock_repo.claim_staff_link = AsyncMock(return_value=StaffLinkClaimResult(ok=True))

    with (
        patch(
            "services.auth.dingtalk_bind_service.try_acquire_pair_claim_lock",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "services.auth.dingtalk_bind_service.release_pair_claim_lock",
            new_callable=AsyncMock,
        ),
        patch(
            "services.auth.dingtalk_bind_service.get_bind_token_consumed",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "services.auth.dingtalk_bind_service.get_bind_token_data",
            new_callable=AsyncMock,
            return_value=payload,
        ),
        patch(
            "services.auth.dingtalk_bind_service.is_bind_code_guess_blocked",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "services.auth.dingtalk_bind_service.rls_async_session",
        ) as mock_rls,
        patch(
            "services.auth.dingtalk_bind_service.DingtalkStaffLinkRepository",
            return_value=mock_repo,
        ),
        patch(
            "services.auth.dingtalk_bind_service.consume_bind_token",
            new_callable=AsyncMock,
            return_value=payload,
        ) as mock_consume,
        patch(
            "services.auth.dingtalk_bind_service.clear_bind_code_guess_failures",
            new_callable=AsyncMock,
        ),
        patch(
            "services.auth.dingtalk_bind_service.force_burn_bind_token",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_rls.return_value = mock_cm

        ok, err = await claim_dingtalk_qr_bind(
            token=token,
            bind_code=bind_code,
            organization_id=5,
            dingtalk_staff_id="staffA",
        )

    assert ok is True
    assert err == ""
    mock_db.commit.assert_awaited_once()
    mock_consume.assert_awaited_once_with(token)


@pytest.mark.asyncio
async def test_integrity_error_maps_to_staff_taken() -> None:
    """Concurrent claim races surface as staff taken, not HTTP 500."""
    token = "test-bind-token-jkl"
    secret = "race-secret-material"
    bind_code = _valid_bind_code(secret, token)
    payload = {
        "user_id": 42,
        "organization_id": 5,
        "bind_code_secret": secret,
    }

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock(side_effect=IntegrityError("stmt", {}, Exception("dup")))
    mock_repo = MagicMock()
    mock_repo.get_by_staff = AsyncMock(return_value=None)
    mock_repo.claim_staff_link = AsyncMock(return_value=StaffLinkClaimResult(ok=True))

    with (
        patch(
            "services.auth.dingtalk_bind_service.try_acquire_pair_claim_lock",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "services.auth.dingtalk_bind_service.release_pair_claim_lock",
            new_callable=AsyncMock,
        ),
        patch(
            "services.auth.dingtalk_bind_service.get_bind_token_consumed",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "services.auth.dingtalk_bind_service.get_bind_token_data",
            new_callable=AsyncMock,
            return_value=payload,
        ),
        patch(
            "services.auth.dingtalk_bind_service.is_bind_code_guess_blocked",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "services.auth.dingtalk_bind_service.rls_async_session",
        ) as mock_rls,
        patch(
            "services.auth.dingtalk_bind_service.DingtalkStaffLinkRepository",
            return_value=mock_repo,
        ),
        patch(
            "services.auth.dingtalk_bind_service.consume_bind_token",
            new_callable=AsyncMock,
        ) as mock_consume,
    ):
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_rls.return_value = mock_cm

        ok, err = await claim_dingtalk_qr_bind(
            token=token,
            bind_code=bind_code,
            organization_id=5,
            dingtalk_staff_id="staffA",
        )

    assert ok is False
    assert err == BIND_ERROR_STAFF_TAKEN
    mock_consume.assert_not_called()


@pytest.mark.asyncio
async def test_consumed_token_returns_without_consume_retry() -> None:
    """Already-consumed tokens short-circuit before claim."""
    with (
        patch(
            "services.auth.dingtalk_bind_service.get_bind_token_consumed",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "services.auth.dingtalk_bind_service.consume_bind_token",
            new_callable=AsyncMock,
        ) as mock_consume,
    ):
        ok, err = await claim_dingtalk_qr_bind(
            token="used-token",
            bind_code="123456",
            organization_id=5,
            dingtalk_staff_id="staffA",
        )

    assert ok is False
    assert err == BIND_ERROR_TOKEN_CONSUMED
    mock_consume.assert_not_called()
