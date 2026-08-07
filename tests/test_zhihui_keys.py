"""Unit tests for ZhiHui storage key helpers."""

from services.zhihui.storage.keys import (
    LOGICAL_PREFIX,
    build_generation_key,
    is_zhihui_generation_key,
    is_zhihui_logical_key,
    zhihui_public_asset_url,
)


def test_build_generation_key_default_jpg() -> None:
    """Generation keys live under zhihui/generations/{uuid}.jpg."""
    key = build_generation_key(generation_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    assert key == f"{LOGICAL_PREFIX}/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.jpg"
    assert is_zhihui_logical_key(key)
    assert is_zhihui_generation_key(key)


def test_is_zhihui_logical_key_rejects_traversal() -> None:
    """Reject paths outside the generations prefix (including legacy seed keys)."""
    assert not is_zhihui_logical_key("showcase/posts/x.jpg")
    assert not is_zhihui_logical_key("zhihui/generations/../secret.jpg")
    assert not is_zhihui_logical_key("zhihui/generations/not-a-uuid.txt/extra")
    assert not is_zhihui_logical_key("zhihui/seeds/seed-1.jpg")
    assert not is_zhihui_logical_key("zhihui/seeds/../secret.jpg")


def test_zhihui_public_asset_url() -> None:
    """Public asset URLs are app-relative under /api/zhihui/assets/."""
    key = f"{LOGICAL_PREFIX}/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.jpg"
    assert zhihui_public_asset_url(key) == f"/api/zhihui/assets/{key}"
