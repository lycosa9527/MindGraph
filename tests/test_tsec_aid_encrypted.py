"""T-Sec AppId ciphertext: cycle-pad, expire cap, unique IV, route gate."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from fastapi import HTTPException

from routers.auth.tsec import get_tsec_aid_encrypted
from services.auth.tsec.aid_encrypted import (
    AES_IV_LEN,
    AES_KEY_LEN,
    MAX_EXPIRE_SECONDS,
    AidEncryptedError,
    clamp_expire_seconds,
    cycle_pad_app_secret_key,
    mint_aid_encrypted,
)


def _decrypt_aid(token: str, secret: str) -> str:
    """Round-trip helper for tests only."""
    raw = base64.b64decode(token)
    init_vector, ciphertext = raw[:AES_IV_LEN], raw[AES_IV_LEN:]
    key = cycle_pad_app_secret_key(secret)
    cipher = AES.new(key, AES.MODE_CBC, init_vector)
    return unpad(cipher.decrypt(ciphertext), AES.block_size).decode("utf-8")


def test_cycle_pad_short_key_is_32_bytes() -> None:
    """Keys shorter than 32 cycle-pad; a 16-byte key must not stay 16."""
    padded_16 = cycle_pad_app_secret_key("a" * 16)
    padded_25 = cycle_pad_app_secret_key("abcdefghijklmnopqrstuvwxy")
    assert len(padded_16) == AES_KEY_LEN
    assert len(padded_25) == AES_KEY_LEN
    assert padded_16 == (b"a" * AES_KEY_LEN)
    assert padded_25 == b"abcdefghijklmnopqrstuvwxyabcdefg"


def test_cycle_pad_long_key_truncated_to_32() -> None:
    """AES-256 uses the first 32 bytes when AppSecretKey is longer."""
    raw = "x" * 40
    assert cycle_pad_app_secret_key(raw) == raw[:AES_KEY_LEN].encode("utf-8")


def test_clamp_expire_caps_at_one_day() -> None:
    """Tencent expire must stay in [1, 86400]."""
    assert clamp_expire_seconds(0) == 1
    assert clamp_expire_seconds(999999) == MAX_EXPIRE_SECONDS
    assert clamp_expire_seconds(300) == 300


def test_mint_plaintext_and_unique_iv() -> None:
    """CBC mint recovers {appId}&{cur}&{expire}; each call uses a new IV."""
    secret = "test-app-secret-key-25ch"
    first = mint_aid_encrypted("199999164", secret, expire_seconds=300, now_unix=1_700_000_000)
    second = mint_aid_encrypted("199999164", secret, expire_seconds=300, now_unix=1_700_000_000)
    assert first["aid_encrypted_type"] == "cbc"
    assert first["aid_encrypted"] != second["aid_encrypted"]
    first_iv = base64.b64decode(first["aid_encrypted"])[:AES_IV_LEN]
    second_iv = base64.b64decode(second["aid_encrypted"])[:AES_IV_LEN]
    assert first_iv != second_iv
    assert _decrypt_aid(first["aid_encrypted"], secret) == "199999164&1700000000&300"


def test_mint_expire_overflow_is_clamped() -> None:
    """Requested expire above 86400 is written as 86400."""
    secret = "test-app-secret-key-25ch"
    minted = mint_aid_encrypted(
        "199999164",
        secret,
        expire_seconds=999999,
        now_unix=1_700_000_000,
    )
    assert _decrypt_aid(minted["aid_encrypted"], secret) == "199999164&1700000000&86400"


def test_mint_rejects_empty_secret() -> None:
    """Empty AppSecretKey must not produce a token."""
    with pytest.raises(AidEncryptedError):
        mint_aid_encrypted("199999164", "")


@pytest.mark.asyncio
async def test_aid_encrypted_404_when_provider_is_legacy(monkeypatch) -> None:
    """Mint route is hidden unless T-Sec is the effective provider."""
    monkeypatch.setenv("CAPTCHA_PROVIDER", "legacy")
    request = MagicMock()
    request.cookies = {}
    request.headers = {}
    with pytest.raises(HTTPException) as exc_info:
        await get_tsec_aid_encrypted(request, MagicMock(), None)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_aid_encrypted_returns_cbc_token(monkeypatch) -> None:
    """Live tsec provider mints a non-cacheable CBC token."""
    monkeypatch.setenv("CAPTCHA_PROVIDER", "tsec")
    monkeypatch.setenv("TENCENT_CAPTCHA_APP_ID", "199999164")
    monkeypatch.setenv("TENCENT_CAPTCHA_APP_SECRET_KEY", "test-app-secret-key-25ch")
    monkeypatch.setenv("TENCENT_CAPTCHA_SECRET_ID", "AKIDtest")
    monkeypatch.setenv("TENCENT_CAPTCHA_SECRET_KEY", "test-cam-secret")
    request = MagicMock()
    request.cookies = {}
    request.headers = {}
    response = MagicMock()
    response.headers = {}
    with patch(
        "routers.auth.tsec.check_captcha_rate_limit",
        new_callable=AsyncMock,
        return_value=(True, 0),
    ):
        body = await get_tsec_aid_encrypted(request, response, None)
    assert body.aid_encrypted_type == "cbc"
    assert body.aid_encrypted
    assert response.headers["Cache-Control"] == "no-store"
