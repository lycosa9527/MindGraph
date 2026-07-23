"""CSP host-sources and SPA document CSP handling for Showcase COS uploads."""

from __future__ import annotations

from services.infrastructure.utils.spa_handler import (
    inject_csp_nonce,
    strip_document_csp_meta,
)
from services.utils import tencent_cos_client as cos_mod


def test_cos_browser_csp_sources_exact_when_bucket_region_set(monkeypatch) -> None:
    monkeypatch.setattr(cos_mod, "COS_BUCKET", "mindgraph-1356113246")
    monkeypatch.setattr(cos_mod, "COS_REGION", "ap-beijing")
    assert cos_mod.cos_browser_csp_sources() == (
        "https://mindgraph-1356113246.cos.ap-beijing.myqcloud.com "
        "https://mindgraph-1356113246.cos.ap-beijing.tencentcos.cn"
    )


def test_cos_browser_csp_sources_wildcard_fallback(monkeypatch) -> None:
    monkeypatch.setattr(cos_mod, "COS_BUCKET", "")
    monkeypatch.setattr(cos_mod, "COS_REGION", "ap-beijing")
    assert cos_mod.cos_browser_csp_sources() == ("https://*.myqcloud.com https://*.tencentcos.cn")


def test_strip_document_csp_meta_removes_multiline_tag() -> None:
    html = (
        "<!doctype html><head>"
        '<meta charset="UTF-8" />'
        "<meta\n"
        '      http-equiv="Content-Security-Policy"\n'
        "      content=\"default-src 'self'; "
        "connect-src 'self' https://*.myqcloud.com;\" />\n"
        "<title>x</title></head><body></body>"
    )
    stripped = strip_document_csp_meta(html)
    assert "Content-Security-Policy" not in stripped
    assert 'charset="UTF-8"' in stripped
    assert "<title>x</title>" in stripped


def test_inject_nonce_then_strip_meta_keeps_script_nonce() -> None:
    html = (
        "<!doctype html><head>"
        '<meta http-equiv="Content-Security-Policy" '
        "content=\"script-src 'self' 'unsafe-inline'; connect-src 'self';\" />"
        "<script>window.__MG__=1</script>"
        "</head><body></body>"
    )
    stamped = inject_csp_nonce(html, "abcNonce")
    final = strip_document_csp_meta(stamped)
    assert 'nonce="abcNonce"' in final
    assert "Content-Security-Policy" not in final
    assert "window.__MG__=1" in final
