"""Verify Alipay async notification signatures (RSA2 / SHA256)."""

import base64
import logging
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

logger = logging.getLogger(__name__)


def _build_sign_message(params: Mapping[str, Any]) -> bytes:
    """Build the string Alipay signs for async notify (sorted key=value)."""
    filtered: dict[str, str] = {}
    for key, raw in params.items():
        if key in ("sign", "sign_type"):
            continue
        if raw is None or raw == "":
            continue
        if isinstance(raw, (list, tuple)) and raw:
            value = raw[0] if isinstance(raw[0], str) else str(raw[0])
        else:
            value = str(raw)
        filtered[str(key)] = value
    pairs = sorted(filtered.items(), key=lambda item: item[0])
    text = "&".join(f"{k}={v}" for k, v in pairs)
    return text.encode("utf-8")


def _load_public_key(pem_or_b64: str):
    raw = pem_or_b64.strip()
    if "BEGIN PUBLIC KEY" in raw or "BEGIN RSA PUBLIC KEY" in raw:
        return serialization.load_pem_public_key(raw.encode("utf-8"))
    wrapped = (
        "-----BEGIN PUBLIC KEY-----\n"
        + "\n".join(raw[i : i + 64] for i in range(0, len(raw), 64))
        + "\n-----END PUBLIC KEY-----"
    )
    return serialization.load_pem_public_key(wrapped.encode("utf-8"))


def verify_async_notify(params: Mapping[str, Any], alipay_public_key_material: str) -> bool:
    """Return True if ``sign`` matches RSA2 (SHA256) over sorted parameters."""
    sign = params.get("sign")
    if not sign or not isinstance(sign, str):
        return False
    sign_type = str(params.get("sign_type", "")).upper()
    if sign_type and "RSA2" not in sign_type:
        logger.warning("[Markets] Unsupported Alipay sign_type: %s", sign_type)
        return False
    message = _build_sign_message(params)
    try:
        signature = base64.b64decode(sign)
        public_key = _load_public_key(alipay_public_key_material)
        public_key.verify(
            signature,
            message,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except (InvalidSignature, ValueError, TypeError) as exc:
        logger.warning("[Markets] Alipay notify verify failed: %s", exc)
        return False
