"""Pinned-vector tests for Tencent VOD client upload HMAC-SHA1."""

from __future__ import annotations

import base64
import hashlib
import hmac

from services.features.vod.upload_sign import (
    MAX_UPLOAD_TTL_SECONDS,
    build_client_upload_signature,
    build_upload_original,
    clamp_upload_ttl,
    sign_upload_original,
)

# Official 266/10638 Python sample (required four fields only).
OFFICIAL_SECRET_ID = "IamSecretId"
OFFICIAL_SECRET_KEY = "IamSecretKey"
OFFICIAL_TIMESTAMP = 1571215095
OFFICIAL_EXPIRE = OFFICIAL_TIMESTAMP + 86400 * 365 * 10
OFFICIAL_RANDOM = 220625


def test_official_original_query_string() -> None:
    """Required four fields match the official QueryString order."""
    original = build_upload_original(
        OFFICIAL_SECRET_ID,
        OFFICIAL_TIMESTAMP,
        OFFICIAL_EXPIRE,
        OFFICIAL_RANDOM,
        one_time_valid=0,
    )
    assert original == (
        f"secretId={OFFICIAL_SECRET_ID}"
        f"&currentTimeStamp={OFFICIAL_TIMESTAMP}"
        f"&expireTime={OFFICIAL_EXPIRE}"
        f"&random={OFFICIAL_RANDOM}"
    )


def test_official_hmac_sha1_base64_vector() -> None:
    """HMAC-SHA1 digest concatenated with original, then Base64."""
    original = build_upload_original(
        OFFICIAL_SECRET_ID,
        OFFICIAL_TIMESTAMP,
        OFFICIAL_EXPIRE,
        OFFICIAL_RANDOM,
        one_time_valid=0,
    )
    digest = hmac.new(
        OFFICIAL_SECRET_KEY.encode("utf-8"),
        original.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    expected = base64.b64encode(digest + original.encode("utf-8")).decode("ascii")
    assert sign_upload_original(original, OFFICIAL_SECRET_KEY) == expected
    assert (
        build_client_upload_signature(
            OFFICIAL_SECRET_ID,
            OFFICIAL_SECRET_KEY,
            OFFICIAL_TIMESTAMP,
            OFFICIAL_EXPIRE,
            OFFICIAL_RANDOM,
            one_time_valid=0,
        )
        == expected
    )


def test_one_time_valid_and_sub_app_appended() -> None:
    """Optional procedure, SubAppId, oneTimeValid, and sourceContext append."""
    original = build_upload_original(
        OFFICIAL_SECRET_ID,
        OFFICIAL_TIMESTAMP,
        OFFICIAL_EXPIRE,
        OFFICIAL_RANDOM,
        procedure="LongVideoPreset",
        vod_sub_app_id=1500005696,
        one_time_valid=1,
        source_context="org:5:user:1:media:abc",
    )
    assert "oneTimeValid=1" in original
    assert "procedure=LongVideoPreset" in original
    assert "vodSubAppId=1500005696" in original
    assert "sourceContext=org%3A5%3Auser%3A1%3Amedia%3Aabc" in original


def test_upload_ttl_clamped_to_official_max() -> None:
    """Upload TTL is at least 1 second and at most 90 days."""
    assert clamp_upload_ttl(0) == 1
    assert clamp_upload_ttl(MAX_UPLOAD_TTL_SECONDS + 10) == MAX_UPLOAD_TTL_SECONDS
    assert clamp_upload_ttl(7200) == 7200
