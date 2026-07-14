"""Tests for COS_SYNC_KEY_PREFIX and sync object keys."""

from __future__ import annotations

from unittest.mock import patch

from services.infrastructure.sync import cos_sync_env


def test_normalized_cos_sync_prefix_uses_dedicated_env():
    with patch.dict(
        "os.environ",
        {"COS_SYNC_KEY_PREFIX": "backups/mindgraph-shared"},
        clear=False,
    ):
        assert cos_sync_env.normalized_cos_sync_prefix() == "backups/mindgraph-shared"
        assert cos_sync_env.crowdsec_blocklist_cos_key() == ("backups/mindgraph-shared/sync/crowdsec/blocklist.txt")
        assert cos_sync_env.abuseipdb_meta_cos_key() == ("backups/mindgraph-shared/sync/abuseipdb/meta.json")
        assert cos_sync_env.geolite_mmdb_cos_key() == ("backups/mindgraph-shared/sync/geolite/GeoLite2-Country.mmdb")


def test_cos_config_snapshot_includes_sync_key_prefix():
    with patch.dict(
        "os.environ",
        {
            "COS_SYNC_KEY_PREFIX": "backups/mindgraph-shared",
            "COS_SYNC_ENABLED": "false",
        },
        clear=False,
    ):
        snap = cos_sync_env.cos_config_snapshot()
    assert snap["sync_key_prefix"] == "backups/mindgraph-shared"
    assert "default_sync_key_prefix" in snap
