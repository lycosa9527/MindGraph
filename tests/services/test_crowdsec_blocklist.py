"""Tests for CrowdSec blocklist URL building and enable flags."""

from __future__ import annotations

import pytest

from services.infrastructure.security import crowdsec_blocklist_service


class TestCrowdsecBlocklistConfig:
    def test_disabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CROWDSEC_BLOCKLIST_ENABLED", raising=False)
        assert not crowdsec_blocklist_service.crowdsec_blocklist_master_enabled()

    def test_enabled_requires_credentials_and_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CROWDSEC_BLOCKLIST_ENABLED", "true")
        monkeypatch.setenv("CROWDSEC_BLOCKLIST_USERNAME", "u")
        monkeypatch.setenv("CROWDSEC_BLOCKLIST_PASSWORD", "p")
        monkeypatch.setenv(
            "CROWDSEC_BLOCKLIST_URL",
            "https://admin.api.crowdsec.net/v1/integrations/x/content",
        )
        assert crowdsec_blocklist_service.crowdsec_blocklist_master_enabled()

    def test_integration_id_builds_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CROWDSEC_BLOCKLIST_ENABLED", "true")
        monkeypatch.setenv("CROWDSEC_BLOCKLIST_USERNAME", "u")
        monkeypatch.setenv("CROWDSEC_BLOCKLIST_PASSWORD", "p")
        monkeypatch.delenv("CROWDSEC_BLOCKLIST_URL", raising=False)
        monkeypatch.setenv("CROWDSEC_BLOCKLIST_INTEGRATION_ID", "abc-123")
        assert crowdsec_blocklist_service.crowdsec_blocklist_master_enabled()
        assert crowdsec_blocklist_service.build_crowdsec_blocklist_content_url() == (
            "https://admin.api.crowdsec.net/v1/integrations/abc-123/content"
        )

    def test_default_baseline_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CROWDSEC_BASELINE_FILE", raising=False)
        path = crowdsec_blocklist_service.crowdsec_baseline_blacklist_path()
        assert path.name == "blocklist_baseline.txt"
        assert "data" in path.parts and "crowdsec" in path.parts

    def test_sync_interval_default_daily(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CROWDSEC_BLOCKLIST_SYNC_INTERVAL_SECONDS", raising=False)
        assert crowdsec_blocklist_service.get_crowdsec_sync_interval_seconds() == 86400

    def test_sync_interval_clamps_below_daily(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CROWDSEC_BLOCKLIST_SYNC_INTERVAL_SECONDS", "3600")
        assert crowdsec_blocklist_service.get_crowdsec_sync_interval_seconds() == 86400
