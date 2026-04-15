"""MindBot long-lived map bounds and admin snapshot (memory footprint)."""

from __future__ import annotations


def test_oauth_lock_map_lru_evicts_oldest(monkeypatch) -> None:
    """LRU eviction keeps the in-process OAuth lock map at configured max."""
    import services.mindbot.platforms.dingtalk.auth.oauth as oauth_mod

    monkeypatch.setenv("MINDBOT_OAUTH_LOCK_MAP_MAX", "2")
    oauth_mod._oauth_lock_map_max_entries.cache_clear()
    oauth_mod._token_fetch_locks.clear()

    oauth_mod._get_token_lock("mindbot:test:key_a")
    oauth_mod._get_token_lock("mindbot:test:key_b")
    assert oauth_mod.oauth_lock_map_size() == 2

    oauth_mod._get_token_lock("mindbot:test:key_c")
    assert oauth_mod.oauth_lock_map_size() == 2
    assert "mindbot:test:key_a" not in oauth_mod._token_fetch_locks
    assert "mindbot:test:key_c" in oauth_mod._token_fetch_locks


def test_mindbot_long_lived_maps_snapshot_shape() -> None:
    from services.mindbot.telemetry.metrics import mindbot_long_lived_maps_snapshot

    snap = mindbot_long_lived_maps_snapshot()
    assert snap["oauth_lock_map_size"] >= 0
    assert snap["oauth_lock_map_max"] >= 2
    assert snap["dingtalk_stream_registered_clients"] >= 0
