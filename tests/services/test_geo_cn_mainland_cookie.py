"""Tests for signed mainland-China observation cookie."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import Request

from services.auth.geo_cn_mainland_cookie import (
    GEO_CN_MAINLAND_COOKIE_NAME,
    json_forbidden_cn_geo,
    set_geo_cn_mainland_cookie,
    verify_geo_cn_mainland_cookie,
)


def test_verify_rejects_empty() -> None:
    assert verify_geo_cn_mainland_cookie(None) is False
    assert verify_geo_cn_mainland_cookie("") is False


def test_set_and_verify_round_trip() -> None:
    with patch("services.auth.geo_cn_mainland_cookie.get_jwt_secret", return_value="test-secret-key"):
        resp = MagicMock()
        req = MagicMock()
        req.headers = {}
        set_geo_cn_mainland_cookie(resp, req)
        call_kw = resp.set_cookie.call_args.kwargs
        assert call_kw["key"] == GEO_CN_MAINLAND_COOKIE_NAME
        value = call_kw["value"]
        assert verify_geo_cn_mainland_cookie(value) is True
        assert verify_geo_cn_mainland_cookie("wrong") is False


def test_json_forbidden_stamps_when_requested() -> None:
    with patch("services.auth.geo_cn_mainland_cookie.get_jwt_secret", return_value="test-secret-key"):
        req = MagicMock(spec=Request)
        req.headers = {}
        out = json_forbidden_cn_geo("blocked", req, True)
        assert out.status_code == 403
        assert GEO_CN_MAINLAND_COOKIE_NAME in out.headers.get("set-cookie", "")


def test_json_forbidden_no_stamp_when_cookie_only_block() -> None:
    with patch("services.auth.geo_cn_mainland_cookie.get_jwt_secret", return_value="test-secret-key"):
        req = MagicMock(spec=Request)
        req.headers = {}
        out = json_forbidden_cn_geo("blocked", req, False)
        assert out.status_code == 403
        assert "set-cookie" not in (out.headers.get("set-cookie") or "").lower()
