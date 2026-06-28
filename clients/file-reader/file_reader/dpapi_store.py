"""Windows DPAPI helpers for encrypting file-reader credentials at rest."""

from __future__ import annotations

import json
import sys
from typing import Dict

CRYPTPROTECT_UI_FORBIDDEN = 0x01
_IS_WIN32 = sys.platform == "win32"


class DpapiError(OSError):
    """Raised when DPAPI protect/unprotect fails."""


if _IS_WIN32:
    import ctypes
    from ctypes import wintypes

    class _DataBlob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    _windll = getattr(ctypes, "windll", None)
    if _windll is None:
        raise DpapiError("DPAPI requires Windows ctypes.windll")
    _crypt32 = _windll.crypt32
    _kernel32 = _windll.kernel32

    def _bytes_to_blob(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
        buffer = (ctypes.c_byte * len(data)).from_buffer_copy(data)
        blob = _DataBlob(len(data), buffer)
        return blob, buffer

    def _blob_to_bytes(blob: _DataBlob) -> bytes:
        if not blob.pbData or blob.cbData == 0:
            return b""
        return bytes(ctypes.cast(blob.pbData, ctypes.POINTER(ctypes.c_byte * blob.cbData)).contents)

    def _free_blob(blob: _DataBlob) -> None:
        if blob.pbData:
            _kernel32.LocalFree(blob.pbData)

    def dpapi_available() -> bool:
        """Return True when DPAPI can be used on this platform."""
        return True

    def protect_bytes(data: bytes) -> bytes:
        """Encrypt bytes for the current Windows user."""
        blob_in, _keep = _bytes_to_blob(data)
        blob_out = _DataBlob()
        if not _crypt32.CryptProtectData(
            ctypes.byref(blob_in),
            None,
            None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(blob_out),
        ):
            raise DpapiError("CryptProtectData failed")
        try:
            return _blob_to_bytes(blob_out)
        finally:
            _free_blob(blob_out)

    def unprotect_bytes(data: bytes) -> bytes:
        """Decrypt bytes previously protected for the current Windows user."""
        blob_in, _keep = _bytes_to_blob(data)
        blob_out = _DataBlob()
        if not _crypt32.CryptUnprotectData(
            ctypes.byref(blob_in),
            None,
            None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(blob_out),
        ):
            raise DpapiError("CryptUnprotectData failed")
        try:
            return _blob_to_bytes(blob_out)
        finally:
            _free_blob(blob_out)

else:

    def dpapi_available() -> bool:
        """Return True when DPAPI can be used on this platform."""
        return False

    def protect_bytes(data: bytes) -> bytes:
        """Encrypt bytes for the current Windows user."""
        raise DpapiError("DPAPI is only available on Windows")

    def unprotect_bytes(data: bytes) -> bytes:
        """Decrypt bytes previously protected for the current Windows user."""
        raise DpapiError("DPAPI is only available on Windows")


def protect_credentials(api_token: str, account_phone: str) -> bytes:
    """Serialize and DPAPI-encrypt credential fields."""
    payload = json.dumps(
        {"api_token": api_token, "account_phone": account_phone},
        separators=(",", ":"),
    ).encode("utf-8")
    return protect_bytes(payload)


def unprotect_credentials(blob: bytes) -> Dict[str, str]:
    """DPAPI-decrypt credential fields."""
    raw = unprotect_bytes(blob).decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise DpapiError("Invalid credential payload")
    return {
        "api_token": str(data.get("api_token") or ""),
        "account_phone": str(data.get("account_phone") or ""),
    }
