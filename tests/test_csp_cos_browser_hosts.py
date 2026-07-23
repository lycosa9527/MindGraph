"""CSP host-sources for Showcase browser→COS uploads."""

from __future__ import annotations

from services.infrastructure.utils.spa_handler import (
    ensure_csp_meta_cos_hosts,
    inject_csp_nonce,
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


def test_ensure_csp_meta_cos_hosts_appends_connect_and_media() -> None:
    html = (
        "<!doctype html><head>"
        '<meta http-equiv="Content-Security-Policy" '
        "content=\"default-src 'self'; "
        "connect-src 'self' ws: wss: blob:; "
        "frame-src 'self';\" />"
        "</head><body></body>"
    )
    hosts = (
        "https://mindgraph-1356113246.cos.ap-beijing.myqcloud.com "
        "https://mindgraph-1356113246.cos.ap-beijing.tencentcos.cn"
    )
    updated = ensure_csp_meta_cos_hosts(html, hosts)
    assert "connect-src 'self' ws: wss: blob: " + hosts.split(" ", maxsplit=1)[0] in updated
    assert "media-src 'self' blob: " + hosts.split(" ", maxsplit=1)[0] in updated
    assert "myqcloud.com" in updated
    assert "tencentcos.cn" in updated


def test_ensure_csp_meta_cos_hosts_idempotent() -> None:
    html = (
        '<meta http-equiv="Content-Security-Policy" '
        "content=\"connect-src 'self' https://*.myqcloud.com; "
        "media-src 'self' blob: https://*.myqcloud.com;\" />"
    )
    once = ensure_csp_meta_cos_hosts(html, "https://bucket.cos.ap-beijing.myqcloud.com")
    twice = ensure_csp_meta_cos_hosts(once, "https://bucket.cos.ap-beijing.myqcloud.com")
    assert once == twice
    # Existing wildcard markers skip further appends on both directives.
    assert once == html


def test_inject_csp_nonce_then_cos_hosts_keeps_nonce() -> None:
    html = (
        "<!doctype html><head>"
        '<meta http-equiv="Content-Security-Policy" '
        "content=\"default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "connect-src 'self';\" />"
        "<script>window.__MG__=1</script>"
        "</head><body></body>"
    )
    stamped = inject_csp_nonce(html, "abcNonce")
    with_cos = ensure_csp_meta_cos_hosts(
        stamped,
        "https://bucket.cos.ap-beijing.myqcloud.com",
    )
    assert "nonce-abcNonce" in with_cos
    assert 'nonce="abcNonce"' in with_cos
    assert "myqcloud.com" in with_cos
