"""Tests for Dify HTTP error mapping."""

from __future__ import annotations

import pytest

from clients.dify import (
    DifyAPIError,
    DifyInvalidParamError,
    DifyQuotaExceededError,
    DifyS3StorageError,
)
from clients.dify_http_errors import raise_for_dify_http_error


def test_400_invalid_param_raises_typed() -> None:
    with pytest.raises(DifyInvalidParamError):
        raise_for_dify_http_error(400, "bad", "invalid_param", "/chat-messages")


def test_400_quota_raises() -> None:
    with pytest.raises(DifyQuotaExceededError):
        raise_for_dify_http_error(400, "quota", "provider_quota_exceeded", "/chat-messages")


def test_503_s3_raises() -> None:
    with pytest.raises(DifyS3StorageError) as ctx:
        raise_for_dify_http_error(503, "s3 down", "s3_connection_failed", "/files/upload")
    assert ctx.value.error_code == "s3_connection_failed"


def test_unmapped_400_raises_generic() -> None:
    with pytest.raises(DifyAPIError) as ctx:
        raise_for_dify_http_error(400, "other", "unknown_code_xyz", "/chat-messages")
    assert ctx.value.error_code == "unknown_code_xyz"
