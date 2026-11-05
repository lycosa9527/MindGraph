"""Public media URLs use https. Ordinary http links and loopback stay put."""

from utils.public_https_url import (
    normalize_external_base_url,
    upgrade_public_http_url,
    upgrade_public_media_urls_in_text,
)


def test_upgrade_strips_default_http_port() -> None:
    """Port 80 is not kept on the https URL."""
    got = upgrade_public_http_url("http://mg.mindspringedu.com:80/api/temp_images/a.png?sig=1")
    assert got == "https://mg.mindspringedu.com/api/temp_images/a.png?sig=1"


def test_upgrade_leaves_loopback_and_https() -> None:
    """Local dev and already-https links are unchanged."""
    local = "http://127.0.0.1:9527/api/temp_images/a.png"
    assert upgrade_public_http_url(local) == local
    secure = "https://mg.mindspringedu.com/api/temp_images/a.png"
    assert upgrade_public_http_url(secure) == secure


def test_normalize_external_base_url_rewrites_legacy_host() -> None:
    """A legacy mg EXTERNAL_BASE_URL is emitted as www."""
    assert normalize_external_base_url("https://mg.mindspringedu.com") == ("https://www.mindspringedu.com")
    assert normalize_external_base_url("http://mg.mindspringedu.com/api") == ("https://www.mindspringedu.com")


def test_markdown_upgrades_media_and_leaves_other_links() -> None:
    """Only temp-image and Zhihui asset links inside markdown change scheme."""
    text = (
        "see http://example.com/docs\n"
        "![](http://mg.mindspringedu.com/api/temp_images/a.png?sig=1)\n"
        "[asset](http://mg.mindspringedu.com/api/zhihui/assets/k.png?sig=2)"
    )
    got = upgrade_public_media_urls_in_text(text)
    assert "http://example.com/docs" in got
    assert "https://www.mindspringedu.com/api/temp_images/a.png?sig=1" in got
    assert "https://www.mindspringedu.com/api/zhihui/assets/k.png?sig=2" in got
