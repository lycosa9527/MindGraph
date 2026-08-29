"""Encrypt/decrypt stored mgat_ secrets for account-modal display."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.domain.user_api_token import UserAPIToken
from services.auth.user_api_token_issue import (
    IssuedUserApiToken,
    ensure_user_api_token,
    reveal_stored_user_api_token,
)
from services.auth.user_api_token_secret import decrypt_user_api_token, encrypt_user_api_token


def test_encrypt_decrypt_roundtrip() -> None:
    """Stored ciphertext must return the same raw token."""
    raw = "mgat_" + "ab" * 32
    with patch(
        "services.auth.user_api_token_secret.get_jwt_secret",
        return_value="unit-test-jwt-secret",
    ):
        blob = encrypt_user_api_token(raw)
        assert blob != raw
        assert decrypt_user_api_token(blob) == raw


def test_decrypt_accepts_previous_jwt_secret() -> None:
    """A JWT rotation must still reveal the stored token."""
    raw = "mgat_" + "cd" * 32
    with patch(
        "services.auth.user_api_token_secret.get_jwt_secret",
        return_value="old-jwt-secret",
    ):
        blob = encrypt_user_api_token(raw)
    with (
        patch(
            "services.auth.user_api_token_secret.get_jwt_secret",
            return_value="new-jwt-secret",
        ),
        patch(
            "services.auth.user_api_token_secret.get_jwt_secret_previous",
            return_value="old-jwt-secret",
        ),
    ):
        assert decrypt_user_api_token(blob) == raw


def test_decrypt_rejects_garbage() -> None:
    """Bad blobs must not raise."""
    with patch(
        "services.auth.user_api_token_secret.get_jwt_secret",
        return_value="unit-test-jwt-secret",
    ):
        assert decrypt_user_api_token("") is None
        assert decrypt_user_api_token("not-valid-base64!!!") is None


def test_reveal_skips_hash_only_and_expired_rows() -> None:
    """Old hash-only rows and expired rows stay hidden."""
    now = datetime.now(UTC)
    hash_only = SimpleNamespace(
        is_active=True,
        expires_at=now + timedelta(days=1),
        token_ciphertext=None,
    )
    expired = SimpleNamespace(
        is_active=True,
        expires_at=now - timedelta(days=1),
        token_ciphertext="abc",
    )
    assert reveal_stored_user_api_token(cast(UserAPIToken, hash_only)) is None
    assert reveal_stored_user_api_token(cast(UserAPIToken, expired)) is None


@pytest.mark.asyncio
async def test_ensure_reuses_live_token_without_minting() -> None:
    """Skill zip download must reuse the visible token, not rotate it."""
    live = IssuedUserApiToken(
        token="mgat_reuse_existing",
        account="13800000000",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        minted=False,
    )
    issue = AsyncMock()
    with (
        patch(
            "services.auth.user_api_token_issue.peek_live_user_api_token",
            AsyncMock(return_value=live),
        ),
        patch("services.auth.user_api_token_issue.issue_user_api_token", issue),
    ):
        out = await ensure_user_api_token(MagicMock(), MagicMock())
    assert out.token == "mgat_reuse_existing"
    issue.assert_not_called()
