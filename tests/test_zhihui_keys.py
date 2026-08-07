"""Unit tests for ZhiHui storage key helpers."""

from services.zhihui.storage.keys import (
    LANDING_SEED_FILENAMES,
    LOGICAL_PREFIX,
    SEEDS_PREFIX,
    build_generation_key,
    build_seed_key,
    is_zhihui_generation_key,
    is_zhihui_logical_key,
    is_zhihui_seed_key,
    zhihui_public_asset_url,
)


def test_build_generation_key_default_jpg() -> None:
    """Generation keys live under zhihui/generations/{uuid}.jpg."""
    key = build_generation_key(generation_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    assert key == f"{LOGICAL_PREFIX}/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.jpg"
    assert is_zhihui_logical_key(key)
    assert is_zhihui_generation_key(key)
    assert not is_zhihui_seed_key(key)


def test_build_seed_key() -> None:
    """Landing seeds use stable zhihui/seeds/seed-N.jpg keys."""
    key = build_seed_key("seed-1.jpg")
    assert key == f"{SEEDS_PREFIX}/seed-1.jpg"
    assert is_zhihui_seed_key(key)
    assert is_zhihui_logical_key(key)
    assert not is_zhihui_generation_key(key)
    assert len(LANDING_SEED_FILENAMES) == 6


def test_is_zhihui_logical_key_rejects_traversal() -> None:
    """Reject paths outside generations/seeds prefixes."""
    assert not is_zhihui_logical_key("showcase/posts/x.jpg")
    assert not is_zhihui_logical_key("zhihui/generations/../secret.jpg")
    assert not is_zhihui_logical_key("zhihui/generations/not-a-uuid.txt/extra")
    assert not is_zhihui_logical_key("zhihui/seeds/../secret.jpg")
    assert not is_zhihui_logical_key("zhihui/seeds/other.jpg")


def test_zhihui_public_asset_url() -> None:
    """Public asset URLs are app-relative under /api/zhihui/assets/."""
    key = f"{LOGICAL_PREFIX}/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.jpg"
    assert zhihui_public_asset_url(key) == f"/api/zhihui/assets/{key}"
    seed = f"{SEEDS_PREFIX}/seed-2.jpg"
    assert zhihui_public_asset_url(seed) == f"/api/zhihui/assets/{seed}"
