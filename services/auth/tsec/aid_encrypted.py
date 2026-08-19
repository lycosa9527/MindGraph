"""Mint Tencent Captcha AppId ciphertext (CaptchaAppId 强制校验 + 一次一密).

Plaintext is ``{CaptchaAppId}&{unix_seconds}&{expire_seconds}``. The key is
AppSecretKey, cycle-padded to 32 bytes when shorter (Java-style; not the
official Python ``32 % len`` remainder, which leaves a 16-byte key unchanged).

CBC default: AES-256-CBC + PKCS7. IV is ``os.urandom(16)`` on every mint so
ciphertext is never reused. ``aidEncrypted`` is Base64(IV || ciphertext).
"""

from __future__ import annotations

import base64
import os
import time
from typing import Literal, TypedDict

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

AES_KEY_LEN = 32
AES_IV_LEN = 16
MAX_EXPIRE_SECONDS = 86400
DEFAULT_EXPIRE_SECONDS = 300
AID_ENCRYPTED_TYPE: Literal["cbc"] = "cbc"


class AidEncryptedError(Exception):
    """AppId ciphertext could not be minted."""


class AidEncryptedPayload(TypedDict):
    """Public JSON for the TencentCaptcha ``aidEncrypted`` option."""

    aid_encrypted: str
    aid_encrypted_type: Literal["cbc"]


def cycle_pad_app_secret_key(secret: str) -> bytes:
    """Return a 32-byte AES-256 key, cycling a shorter AppSecretKey."""
    raw = secret.encode("utf-8")
    if not raw:
        raise AidEncryptedError("empty_app_secret_key")
    if len(raw) >= AES_KEY_LEN:
        return raw[:AES_KEY_LEN]
    return bytes(raw[index % len(raw)] for index in range(AES_KEY_LEN))


def clamp_expire_seconds(expire_seconds: int) -> int:
    """Keep expire in ``[1, 86400]`` as required by Tencent."""
    return min(max(expire_seconds, 1), MAX_EXPIRE_SECONDS)


def mint_aid_encrypted(
    app_id: str,
    app_secret_key: str,
    *,
    expire_seconds: int = DEFAULT_EXPIRE_SECONDS,
    now_unix: int | None = None,
) -> AidEncryptedPayload:
    """Encrypt a one-time AppId token. Never reuse IV or ciphertext."""
    captcha_app_id = (app_id or "").strip()
    secret = (app_secret_key or "").strip()
    if not captcha_app_id:
        raise AidEncryptedError("empty_app_id")
    expire = clamp_expire_seconds(expire_seconds)
    cur_time = int(time.time()) if now_unix is None else now_unix
    if cur_time < 0:
        raise AidEncryptedError("invalid_cur_time")
    plaintext = f"{captcha_app_id}&{cur_time}&{expire}".encode("utf-8")
    key = cycle_pad_app_secret_key(secret)
    init_vector = os.urandom(AES_IV_LEN)
    cipher = AES.new(key, AES.MODE_CBC, init_vector)
    ciphertext = cipher.encrypt(pad(plaintext, AES.block_size))
    token = base64.b64encode(init_vector + ciphertext).decode("ascii")
    return {
        "aid_encrypted": token,
        "aid_encrypted_type": AID_ENCRYPTED_TYPE,
    }
