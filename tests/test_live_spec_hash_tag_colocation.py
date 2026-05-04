"""Cluster hash-tag alignment for live-spec related keys."""

from __future__ import annotations


def test_live_spec_snapshot_seq_changed_keys_share_code_hash_tag(monkeypatch):
    """With COLLAB_REDIS_HASH_TAGS=1, keys share the same {code} segment."""
    monkeypatch.setenv("COLLAB_REDIS_HASH_TAGS", "1")
    from services.online_collab.redis.online_collab_redis_keys import (
        live_changed_keys_key,
        live_spec_key,
        snapshot_seq_key,
    )

    code = "ABC123"
    tagged = "{" + code + "}"
    assert tagged in live_spec_key(code)
    assert tagged in snapshot_seq_key(code)
    assert tagged in live_changed_keys_key(code)
