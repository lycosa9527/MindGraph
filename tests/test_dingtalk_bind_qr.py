"""Tests for DingTalk bind QR token extraction and rotating codes."""

from services.auth.dingtalk_bind_constants import (
    BIND_PATH_MARKER,
    BIND_QUERY_CODE_PARAM,
    BIND_QUERY_PARAM,
)
from services.auth.quick_register_room_code import (
    current_room_code_from_room_secret,
    verify_room_code_submitted,
)
from services.mindbot.bind.qr_decode import (
    extract_bind_payload_from_text,
    extract_bind_token_from_text,
)


def test_extract_bind_token_from_url() -> None:
    token = "abc123XYZ"
    url = f"https://mindgraph.example{BIND_PATH_MARKER}?{BIND_QUERY_PARAM}={token}"
    assert extract_bind_token_from_text(url) == token


def test_extract_bind_payload_includes_rotating_code() -> None:
    token = "abc123XYZ"
    code = "042816"
    url = f"https://mindgraph.example{BIND_PATH_MARKER}?{BIND_QUERY_PARAM}={token}&{BIND_QUERY_CODE_PARAM}={code}"
    assert extract_bind_payload_from_text(url) == (token, code)


def test_extract_bind_token_ignores_unrelated_urls() -> None:
    assert extract_bind_token_from_text("https://example.com/page") is None


def test_verify_bind_rotating_code_roundtrip() -> None:
    token = "channel-token-xyz"
    secret = "per-token-secret-material"
    code, _step, _next, _now = current_room_code_from_room_secret(secret, token)
    assert len(code) == 6
    assert verify_room_code_submitted(secret, token, code)
