"""Tests for SmartEdu downloader helpers."""

from __future__ import annotations

from file_reader.smartedu.models import SmartEduAsset
from file_reader.smartedu.token_store import append_access_token, nd_auth_header


def test_nd_auth_header() -> None:
    headers = nd_auth_header("token-abc")
    assert headers == 'MAC id="token-abc",nonce="0",mac="0"'


def test_nd_auth_header_empty() -> None:
    assert nd_auth_header("") == ""
    assert nd_auth_header("   ") == ""


def test_append_access_token() -> None:
    url = append_access_token("https://example.com/file.pdf", "tok")
    assert "accessToken=tok" in url


def test_asset_fields() -> None:
    asset = SmartEduAsset(
        asset_id="1",
        title="demo",
        alias="课件",
        resource_type="coursewares",
        format="pdf",
        download_url="https://example.com/a.pdf",
    )
    assert asset.format == "pdf"
