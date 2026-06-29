"""Decrypt WeChat Channels encrypted MP4 headers."""

from __future__ import annotations

_DECRYPT_SIZE = 131072
CHANNELS_ENCRYPTED_HEADER_SIZE = _DECRYPT_SIZE


def hex_to_keystream(text: str) -> bytes:
    """Parse a hex keystream string."""
    cleaned = "".join(text.split())
    if not cleaned:
        return b""
    return bytes.fromhex(cleaned)


def decrypt_channels_header(encrypted_head: bytes, keystream: bytes) -> bytes:
    """XOR-decrypt the leading encrypted portion of a Channels MP4."""
    if not keystream:
        raise ValueError("Missing Channels decrypt keystream")
    decrypt_len = min(len(keystream), len(encrypted_head), _DECRYPT_SIZE)
    if decrypt_len <= 0:
        raise ValueError("Encrypted Channels video is empty")
    return bytes(encrypted_head[index] ^ keystream[index] for index in range(decrypt_len))


def decrypt_channels_video(encrypted: bytes, keystream: bytes) -> bytes:
    """XOR-decrypt the first 128 KB of an encrypted Channels MP4."""
    head = decrypt_channels_header(encrypted, keystream)
    tail_start = min(len(keystream), len(encrypted), _DECRYPT_SIZE)
    return head + encrypted[tail_start:]
