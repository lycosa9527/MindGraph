"""Tests for COS admin service."""

from __future__ import annotations

from unittest.mock import patch

from services.admin import cos_admin_service


def test_get_cos_overview_status_structure():
    with patch.object(
        cos_admin_service.tencent_cos_client,
        "test_cos_connection",
        return_value={
            "ok": True,
            "configured": True,
            "sdk_available": True,
            "bucket": "b",
            "region": "ap-beijing",
            "key_prefix": "pfx",
            "error": None,
        },
    ):
        with patch.object(cos_admin_service.tencent_cos_client, "get_json", return_value=None):
            with patch.object(
                cos_admin_service,
                "get_backup_status",
                return_value={
                    "backups": [],
                    "cos": {"enabled": False, "count": 0, "latest": None},
                },
            ):
                with patch.object(cos_admin_service, "list_cos_backups", return_value=[]):
                    payload = cos_admin_service.get_cos_overview_status()
    assert "connection" in payload
    assert "artifacts" in payload
    assert "celery" in payload["artifacts"]
    assert "abuseipdb" in payload["artifacts"]
    assert "geolite" in payload["artifacts"]
    assert payload["sync_role"] in ("off", "publisher", "consumer")
    assert "sync_key_prefix" in payload["config"]
