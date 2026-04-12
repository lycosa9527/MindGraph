"""
DingTalk open-platform callback crypto (HTTP event subscription / URL verification).

Behavior matches the official reference implementation:
https://github.com/open-dingtalk/DingTalk-Callback-Crypto/blob/main/DingCallbackCrypto3.py

Parameters follow DingTalk docs: ``token`` and ``encoding_aes_key`` from the console;
``owner_key`` is appKey, corpId, or suiteKey depending on app type (same as upstream).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import logging
import string
import struct
import time
from random import choice
from typing import Any

from Crypto.Cipher import AES

logger = logging.getLogger(__name__)


def _decode_encoding_aes_key(encoding_aes_key: str) -> bytes:
    raw = encoding_aes_key.strip()
    pad = "=" * ((4 - len(raw) % 4) % 4)
    return base64.b64decode(raw + pad)


class DingTalkOaCallbackCrypto:
    """Encrypt/decrypt DingTalk open-platform callback payloads (AES-CBC + SHA1)."""

    def __init__(self, token: str, encoding_aes_key: str, owner_key: str) -> None:
        self.encoding_aes_key = encoding_aes_key
        self.owner_key = owner_key
        self.token = token
        self.aes_key = _decode_encoding_aes_key(encoding_aes_key)

    def get_encrypted_map(self, content: str) -> dict[str, Any]:
        """Build JSON body for successful callback acknowledgment (e.g. ``success``)."""
        encrypt_content = self._encrypt(content)
        time_stamp = str(int(time.time()))
        nonce = self._generate_random_key(16)
        sign = self._generate_signature(nonce, time_stamp, self.token, encrypt_content)
        return {
            "msg_signature": sign,
            "encrypt": encrypt_content,
            "timeStamp": time_stamp,
            "nonce": nonce,
        }

    def get_decrypt_msg(
        self,
        msg_signature: str,
        time_stamp: str,
        nonce: str,
        content: str,
    ) -> str:
        """Decrypt and verify an inbound ``encrypt`` field; return plaintext JSON string."""
        sign = self._generate_signature(nonce, time_stamp, self.token, content)
        if msg_signature != sign:
            logger.warning("[MindBot] DingTalk OA callback signature mismatch")
            raise ValueError("signature check error")

        try:
            raw = base64.b64decode(content.encode("UTF-8"))
        except binascii.Error as exc:
            raise ValueError("invalid base64 in encrypt field") from exc
        iv = self.aes_key[:16]
        aes_decode = AES.new(self.aes_key, AES.MODE_CBC, iv)
        decode_res = aes_decode.decrypt(raw)
        pad = int(decode_res[-1])
        if pad > 32:
            raise ValueError("Input is not padded or padding is corrupt")
        decode_res = decode_res[:-pad]
        msg_len = struct.unpack("!i", decode_res[16:20])[0]
        tail = decode_res[(20 + msg_len) :].decode("utf-8")
        if tail != self.owner_key:
            raise ValueError("corpId 校验错误")
        return decode_res[20 : (20 + msg_len)].decode("utf-8")

    def _encrypt(self, content: str) -> str:
        msg_len = self._length(content)
        plain = "".join(
            [
                self._generate_random_key(16),
                msg_len.decode("latin-1"),
                content,
                self.owner_key,
            ]
        )
        content_encode = self._pks7encode(plain)
        iv = self.aes_key[:16]
        aes_encode = AES.new(self.aes_key, AES.MODE_CBC, iv)
        aes_encrypt = aes_encode.encrypt(content_encode.encode("UTF-8"))
        return base64.b64encode(aes_encrypt).decode("UTF-8")

    def _generate_signature(
        self,
        nonce: str,
        timestamp: str,
        token: str,
        msg_encrypt: str,
    ) -> str:
        sign_list = "".join(sorted([nonce, timestamp, token, msg_encrypt]))
        return hashlib.sha1(sign_list.encode()).hexdigest()

    @staticmethod
    def _length(content: str) -> bytes:
        return struct.pack(">l", len(content))

    @staticmethod
    def _pks7encode(content: str) -> str:
        length = len(content)
        output = io.StringIO()
        val = 32 - (length % 32)
        for _ in range(val):
            output.write(f"{val:02x}")
        return content + binascii.unhexlify(output.getvalue()).decode()

    @staticmethod
    def _generate_random_key(
        size: int,
        chars: str = string.ascii_letters + string.ascii_lowercase + string.ascii_uppercase + string.digits,
    ) -> str:
        return "".join(choice(chars) for _ in range(size))
