"""Map server/API failures to stable error codes for localized UI messages."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from file_reader.i18n import I18n


class ErrorCode(str, Enum):
    """Stable error identifiers for the file-reader client."""

    MISSING_CREDENTIALS = "missing_credentials"
    NETWORK = "network"
    AUTH_FAILED = "auth_failed"
    PROFILE_FAILED = "profile_failed"
    FEATURE_DISABLED = "feature_disabled"
    API_MISSING = "api_missing"
    PACKAGES_FAILED = "packages_failed"
    CONNECTION_FAILED = "connection_failed"
    PAIRING_FAILED = "pairing_failed"
    UPLOAD_FAILED = "upload_failed"
    NO_CONTENT = "no_content"
    PARSE_FILE = "parse_file"
    WECHAT_DB_READ = "wechat_db_read"
    CREDENTIALS_ENCRYPT_FAILED = "credentials_encrypt_failed"
    SERVER_URL_INVALID = "server_url_invalid"
    ORG_LOCKED = "org_locked"
    RATE_LIMIT = "rate_limit"
    SERVER = "server"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AppError:
    """Structured error for notifications and status labels."""

    code: ErrorCode
    raw_detail: str = ""
    http_status: Optional[int] = None

    def message(self, i18n: I18n) -> str:
        """Localized user-facing text."""
        key = f"error.{self.code.value}"
        detail = self.raw_detail.strip()
        if self.code == ErrorCode.PACKAGES_FAILED:
            return i18n.translate(key, detail=detail or "—")
        if self.code in (ErrorCode.PAIRING_FAILED, ErrorCode.UPLOAD_FAILED, ErrorCode.PARSE_FILE):
            return i18n.translate(key, detail=detail or "—")
        if self.code == ErrorCode.WECHAT_DB_READ:
            return i18n.translate(key, detail=detail or "—")
        if self.code == ErrorCode.SERVER and self.http_status is not None:
            return i18n.translate(key, status=self.http_status)
        if self.code == ErrorCode.UNKNOWN and detail:
            return i18n.translate(key, detail=detail)
        return i18n.translate(key)


def classify_http_error(status: int, detail: str) -> AppError:
    """Classify an HTTP error response."""
    lowered = detail.lower()
    if status == 401:
        return AppError(code=ErrorCode.AUTH_FAILED, raw_detail=detail)
    if status == 403 and "locked" in lowered:
        return AppError(code=ErrorCode.ORG_LOCKED, raw_detail=detail)
    if status == 403:
        return AppError(code=ErrorCode.AUTH_FAILED, raw_detail=detail)
    if status == 404 and "feature is disabled" in lowered:
        return AppError(code=ErrorCode.FEATURE_DISABLED, raw_detail=detail)
    if status == 404 and "pairing" in lowered:
        return AppError(code=ErrorCode.PAIRING_FAILED, raw_detail=detail)
    if status == 404:
        return AppError(code=ErrorCode.API_MISSING, raw_detail=detail)
    if status == 409 and "pairing" in lowered:
        return AppError(code=ErrorCode.PAIRING_FAILED, raw_detail=detail)
    if status == 422:
        return AppError(code=ErrorCode.UPLOAD_FAILED, raw_detail=detail)
    if status == 429:
        return AppError(code=ErrorCode.RATE_LIMIT, raw_detail=detail)
    if status >= 500:
        return AppError(code=ErrorCode.SERVER, raw_detail=detail, http_status=status)
    if detail:
        return AppError(code=ErrorCode.UNKNOWN, raw_detail=detail, http_status=status)
    return AppError(code=ErrorCode.UNKNOWN, raw_detail=f"HTTP {status}", http_status=status)


def classify_message(detail: str) -> AppError:
    """Classify a plain-text or JSON-parsed error string."""
    if not detail:
        return AppError(code=ErrorCode.CONNECTION_FAILED)
    lowered = detail.lower()
    if "feature is disabled" in lowered:
        return AppError(code=ErrorCode.FEATURE_DISABLED, raw_detail=detail)
    if "not found" in lowered and "package" not in lowered:
        return AppError(code=ErrorCode.API_MISSING, raw_detail=detail)
    if "token" in lowered or "unauthorized" in lowered or "invalid" in lowered:
        return AppError(code=ErrorCode.AUTH_FAILED, raw_detail=detail)
    if "locked" in lowered:
        return AppError(code=ErrorCode.ORG_LOCKED, raw_detail=detail)
    if "too many" in lowered or "rate" in lowered:
        return AppError(code=ErrorCode.RATE_LIMIT, raw_detail=detail)
    return AppError(code=ErrorCode.UNKNOWN, raw_detail=detail)


def classify_network(reason: str) -> AppError:
    """Classify urllib / connection failures."""
    text = reason.strip()
    if not text:
        return AppError(code=ErrorCode.NETWORK)
    return AppError(code=ErrorCode.NETWORK, raw_detail=text)
