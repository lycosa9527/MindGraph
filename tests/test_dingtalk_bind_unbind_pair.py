"""Tests for DingTalk unbind pair claim and claim locking."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.auth.dingtalk_bind_constants import (
    BIND_ERROR_TOKEN_CONSUMED,
    BIND_ERROR_TOKEN_EXPIRED,
    BIND_ERROR_UNBIND_NOT_LINKED,
    BIND_ERROR_UNBIND_STAFF_MISMATCH,
    PAIR_PURPOSE_UNBIND,
)
from services.auth.dingtalk_bind_service import (
    claim_dingtalk_qr_bind,
    claim_dingtalk_unbind_pair,
)
from services.auth.quick_register_room_code import current_room_code_from_room_secret


def _valid_bind_code(secret: str, token: str) -> str:
    code, _, _, _ = current_room_code_from_room_secret(secret, token)
    return code


def _claim_lock_patches(*, lock_acquired: bool = True):
    return (
        patch(
            "services.auth.dingtalk_bind_service.try_acquire_pair_claim_lock",
            new_callable=AsyncMock,
            return_value=lock_acquired,
        ),
        patch(
            "services.auth.dingtalk_bind_service.release_pair_claim_lock",
            new_callable=AsyncMock,
        ),
    )


@pytest.mark.asyncio
async def test_unbind_success_deletes_link_and_consumes() -> None:
    """Unbind pair claim removes staff link after linked staff confirms code."""
    token = "unbind-token-abc"
    secret = "unbind-secret-material"
    bind_code = _valid_bind_code(secret, token)
    payload = {
        "user_id": 42,
        "organization_id": 5,
        "bind_code_secret": secret,
        "pair_purpose": PAIR_PURPOSE_UNBIND,
    }
    link = MagicMock()
    link.dingtalk_staff_id = "staffA"

    mock_db = AsyncMock()
    mock_repo = MagicMock()
    mock_repo.get_for_user = AsyncMock(return_value=link)
    mock_repo.delete_for_user = AsyncMock(return_value=True)

    lock_patch, release_patch = _claim_lock_patches()
    with (
        lock_patch,
        release_patch,
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

        ok, err = await claim_dingtalk_unbind_pair(
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
async def test_unbind_staff_mismatch_does_not_consume() -> None:
    """Wrong DingTalk staff cannot unbind another user's link."""
    token = "unbind-token-def"
    secret = "unbind-secret-two"
    bind_code = _valid_bind_code(secret, token)
    payload = {
        "user_id": 42,
        "organization_id": 5,
        "bind_code_secret": secret,
        "pair_purpose": PAIR_PURPOSE_UNBIND,
    }
    link = MagicMock()
    link.dingtalk_staff_id = "staffOwner"

    mock_db = AsyncMock()
    mock_repo = MagicMock()
    mock_repo.get_for_user = AsyncMock(return_value=link)
    mock_repo.delete_for_user = AsyncMock()

    lock_patch, release_patch = _claim_lock_patches()
    with (
        lock_patch,
        release_patch,
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

        ok, err = await claim_dingtalk_unbind_pair(
            token=token,
            bind_code=bind_code,
            organization_id=5,
            dingtalk_staff_id="staffOther",
        )

    assert ok is False
    assert err == BIND_ERROR_UNBIND_STAFF_MISMATCH
    mock_consume.assert_not_called()
    mock_repo.delete_for_user.assert_not_called()


@pytest.mark.asyncio
async def test_unbind_not_linked_does_not_consume() -> None:
    """Unbind claim fails when the MindGraph user has no link."""
    token = "unbind-token-ghi"
    secret = "unbind-secret-three"
    bind_code = _valid_bind_code(secret, token)
    payload = {
        "user_id": 42,
        "organization_id": 5,
        "bind_code_secret": secret,
        "pair_purpose": PAIR_PURPOSE_UNBIND,
    }

    mock_db = AsyncMock()
    mock_repo = MagicMock()
    mock_repo.get_for_user = AsyncMock(return_value=None)

    lock_patch, release_patch = _claim_lock_patches()
    with (
        lock_patch,
        release_patch,
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

        ok, err = await claim_dingtalk_unbind_pair(
            token=token,
            bind_code=bind_code,
            organization_id=5,
            dingtalk_staff_id="staffA",
        )

    assert ok is False
    assert err == BIND_ERROR_UNBIND_NOT_LINKED
    mock_consume.assert_not_called()


@pytest.mark.asyncio
async def test_claim_lock_contention_returns_expired() -> None:
    """Second concurrent claim gets expired when lock is held."""
    token = "bind-token-lock"
    secret = "lock-secret-material"
    bind_code = _valid_bind_code(secret, token)
    payload = {
        "user_id": 42,
        "organization_id": 5,
        "bind_code_secret": secret,
    }

    lock_patch, release_patch = _claim_lock_patches(lock_acquired=False)
    with (
        lock_patch,
        release_patch,
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
            organization_id=5,
            dingtalk_staff_id="staffA",
        )

    assert ok is False
    assert err == BIND_ERROR_TOKEN_EXPIRED
    mock_consume.assert_not_called()


@pytest.mark.asyncio
async def test_claim_lock_contention_returns_consumed_when_token_used() -> None:
    """When lock fails and token is consumed, surface consumed error."""
    token = "bind-token-used"
    secret = "used-secret-material"
    bind_code = _valid_bind_code(secret, token)
    payload = {
        "user_id": 42,
        "organization_id": 5,
        "bind_code_secret": secret,
    }

    lock_patch, release_patch = _claim_lock_patches(lock_acquired=False)
    with (
        lock_patch,
        release_patch,
        patch(
            "services.auth.dingtalk_bind_service.get_bind_token_consumed",
            new_callable=AsyncMock,
            side_effect=[False, True],
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
            organization_id=5,
            dingtalk_staff_id="staffA",
        )

    assert ok is False
    assert err == BIND_ERROR_TOKEN_CONSUMED
    mock_consume.assert_not_called()
