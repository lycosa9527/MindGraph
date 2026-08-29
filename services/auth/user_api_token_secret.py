"""Encrypt and decrypt stored mgat_ secrets for account-modal display."""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from services.utils.error_types import CRYPTO_DECRYPT_ERRORS
from utils.auth.jwt_secret import get_jwt_secret, get_jwt_secret_previous

_NONCE_LEN = 12


def _aes_key(secret: str) -> bytes:
    """Derive a 32-byte AES key from a JWT secret string."""
    return hashlib.sha256(secret.encode("utf-8")).digest()


def encrypt_user_api_token(raw_token: str) -> str:
    """Return URL-safe ciphertext for a raw mgat_ token."""
    nonce = os.urandom(_NONCE_LEN)
    packed = nonce + AESGCM(_aes_key(get_jwt_secret())).encrypt(
        nonce,
        raw_token.encode("utf-8"),
        None,
    )
    return base64.urlsafe_b64encode(packed).decode("ascii")


def _decrypt_with_secret(packed: bytes, secret: str) -> str | None:
    """Try one derived key. Return None when the tag does not match."""
    nonce, body = packed[:_NONCE_LEN], packed[_NONCE_LEN:]
    try:
        return AESGCM(_aes_key(secret)).decrypt(nonce, body, None).decode("utf-8")
    except CRYPTO_DECRYPT_ERRORS:
        return None


def decrypt_user_api_token(ciphertext: str) -> str | None:
    """Return the raw token, or None when the blob is missing or stale.

    Tries the current JWT secret, then the previous secret so one rotation
    does not hide a live token and force a download mint.
    """
    blob = ciphertext.strip()
    if not blob:
        return None
    try:
        packed = base64.urlsafe_b64decode(blob.encode("ascii"))
    except CRYPTO_DECRYPT_ERRORS:
        return None
    if len(packed) <= _NONCE_LEN:
        return None
    secrets = [get_jwt_secret()]
    previous = get_jwt_secret_previous()
    if previous and previous not in secrets:
        secrets.append(previous)
    for secret in secrets:
        plain = _decrypt_with_secret(packed, secret)
        if plain is not None:
            return plain
    return None
