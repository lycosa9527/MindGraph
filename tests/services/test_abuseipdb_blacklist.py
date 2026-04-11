"""Tests for AbuseIPDB blacklist parsing, sync interval, and rate-limit helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from services.infrastructure.security import abuseipdb_blacklist_parse
from services.infrastructure.security import abuseipdb_service
from services.infrastructure.security import ip_reputation_env_snapshot
from services.infrastructure.security.fail2ban_integration import report_ban


class TestBlacklistPayloadParse:
    def test_official_list_shape(self) -> None:
        payload = {
            "data": [
                {
                    "ipAddress": "1.2.3.4",
                    "abuseConfidenceScore": 100,
                }
            ]
        }
        ips, err = abuseipdb_blacklist_parse.parse_abuseipdb_blacklist_payload(payload)
        assert err is None
        assert ips == {"1.2.3.4"}

    def test_legacy_dict_ips(self) -> None:
        payload = {"data": {"ips": [{"ip": "5.6.7.8"}]}}
        ips, err = abuseipdb_blacklist_parse.parse_abuseipdb_blacklist_payload(payload)
        assert err is None
        assert ips == {"5.6.7.8"}

    def test_plaintext_lines(self) -> None:
        body = "# c\n192.0.2.1\n2001:db8::1\n"
        ips = abuseipdb_blacklist_parse.parse_abuseipdb_blacklist_plaintext(body)
        assert ips == {"192.0.2.1", "2001:db8::1"}

    def test_missing_data_returns_error(self) -> None:
        ips, err = abuseipdb_blacklist_parse.parse_abuseipdb_blacklist_payload({})
        assert err == "missing data"
        assert ips == set()


class TestBlacklistSyncInterval:
    def test_default_daily(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ABUSEIPDB_BLACKLIST_SYNC_INTERVAL_SECONDS", raising=False)
        monkeypatch.delenv("ABUSEIPDB_BLACKLIST_SYNC_RELAX_MIN_INTERVAL", raising=False)
        assert abuseipdb_service.get_blacklist_sync_interval_seconds() == 86400

    def test_clamp_daily_floor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ABUSEIPDB_BLACKLIST_SYNC_INTERVAL_SECONDS", "3600")
        monkeypatch.delenv("ABUSEIPDB_BLACKLIST_SYNC_RELAX_MIN_INTERVAL", raising=False)
        assert abuseipdb_service.get_blacklist_sync_interval_seconds() == 86400

    def test_relax_allows_hourly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ABUSEIPDB_BLACKLIST_SYNC_INTERVAL_SECONDS", "3600")
        monkeypatch.setenv("ABUSEIPDB_BLACKLIST_SYNC_RELAX_MIN_INTERVAL", "true")
        assert abuseipdb_service.get_blacklist_sync_interval_seconds() == 3600


class TestReportBanNormalize:
    def test_normalize_ipv4(self) -> None:
        assert report_ban.normalize_client_ip(" 192.0.2.1 ") == "192.0.2.1"

    def test_normalize_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            report_ban.normalize_client_ip("not-an-ip")


class TestRetryAfterHeader:
    def test_parse_retry_after(self) -> None:
        response = httpx.Response(429, headers={"Retry-After": "120"})
        assert abuseipdb_service.parse_retry_after_seconds(response) == 120

    def test_parse_retry_after_missing(self) -> None:
        response = httpx.Response(429)
        assert abuseipdb_service.parse_retry_after_seconds(response) is None


class TestPipelineSaddChunks:
    def test_empty_batch_returns_zero(self) -> None:
        r = MagicMock()
        assert abuseipdb_service.pipeline_sadd_chunks(r, "k", [], 2000) == 0
        r.pipeline.assert_not_called()

    def test_sums_execute_results(self) -> None:
        r = MagicMock()
        pipe = MagicMock()
        r.pipeline.return_value = pipe
        pipe.execute.return_value = [2, 1, 5]
        total = abuseipdb_service.pipeline_sadd_chunks(
            r,
            "abuseipdb:blacklist:ips",
            ["a", "b", "c", "d", "e"],
            chunk_size=2,
        )
        assert total == 8
        assert pipe.sadd.call_count == 3


class TestIpReputationEnvSnapshot:
    def test_warm_then_blacklist_lookup_matches_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ABUSEIPDB_ENABLED", "true")
        monkeypatch.setenv("ABUSEIPDB_API_KEY", "k")
        monkeypatch.setenv("ABUSEIPDB_BLACKLIST_LOOKUP_ENABLED", "true")
        monkeypatch.delenv("CROWDSEC_BLOCKLIST_ENABLED", raising=False)
        ip_reputation_env_snapshot.warm_ip_reputation_env_snapshot()
        assert ip_reputation_env_snapshot.blacklist_lookup_active() is True
        assert ip_reputation_env_snapshot.should_skip_ip_reputation_middleware() is False


class TestSismemberCacheTtl:
    def test_default_ttl_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("IP_REPUTATION_SISMEMBER_CACHE_TTL_SECONDS", raising=False)
        assert abuseipdb_service.get_ip_reputation_sismember_cache_ttl_seconds() == 0

    def test_warm_ttl_ignores_later_env_change(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IP_REPUTATION_SISMEMBER_CACHE_TTL_SECONDS", "5")
        abuseipdb_service.invalidate_sismember_cache_ttl_snapshot()
        abuseipdb_service.warm_sismember_cache_ttl_snapshot()
        monkeypatch.setenv("IP_REPUTATION_SISMEMBER_CACHE_TTL_SECONDS", "999")
        assert abuseipdb_service.get_ip_reputation_sismember_cache_ttl_seconds() == 5

    def test_clear_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IP_REPUTATION_SISMEMBER_CACHE_TTL_SECONDS", "300")
        abuseipdb_service._sismember_cache_set("192.0.2.1", True)
        abuseipdb_service.clear_ip_reputation_sismember_cache()
        assert abuseipdb_service._sismember_cache_get("192.0.2.1") is None


class TestCanonicalIpForBlacklist:
    def test_ipv4_mapped_normalized(self) -> None:
        assert (
            abuseipdb_service._canonical_ip_for_blacklist_lookup("::ffff:192.0.2.1")
            == "192.0.2.1"
        )

    def test_strips_zone_id(self) -> None:
        out = abuseipdb_service._canonical_ip_for_blacklist_lookup("fe80::1%eth0")
        assert "%" not in out
