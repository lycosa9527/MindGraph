"""WeChat 4.1+ SQLCipher passphrase validation and key derivation."""

from __future__ import annotations

from file_reader.wechat.crypto import (
    derive_enc_key_from_passphrase,
    verify_enc_key,
    verify_passphrase,
)

__all__ = [
    "derive_enc_key_from_passphrase",
    "derive_keys_from_passphrase",
    "verify_passphrase",
]


def derive_keys_from_passphrase(
    passphrase: bytes,
    db_files: list[tuple[str, object, int, str, bytes]],
) -> dict[str, str]:
    """Derive per-salt encryption keys from a WeChat 4.1+ WCDB passphrase."""
    key_map: dict[str, str] = {}
    for _rel, _path, _size, salt_hex, page1 in db_files:
        salt = bytes.fromhex(salt_hex)
        enc_key = derive_enc_key_from_passphrase(passphrase, salt)
        if verify_enc_key(enc_key, page1):
            key_map[salt_hex] = enc_key.hex()
    return key_map
