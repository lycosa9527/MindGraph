"""
Admin COS management service (status aggregation and manual triggers).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict

from services.infrastructure.sync.cos_sync_env import (
    abuseipdb_meta_cos_key,
    celery_meta_cos_key,
    cos_config_snapshot,
    cos_sync_role,
    crowdsec_meta_cos_key,
    geolite_meta_cos_key,
    qdrant_meta_cos_key,
)
from services.infrastructure.sync.abuseipdb_cos_sync import (
    get_abuseipdb_cos_status,
    sync_blacklist_for_role,
)
from services.infrastructure.sync.celery_cos_sync import (
    get_celery_cos_status,
    install_celery_from_cos,
    publish_celery_release_to_cos,
)
from services.infrastructure.sync.crowdsec_cos_sync import (
    get_crowdsec_cos_status,
    merge_crowdsec_blocklist_for_role,
)
from services.infrastructure.sync.geolite_cos_sync import (
    get_geolite_cos_status,
    sync_geolite_for_role,
)
from services.infrastructure.sync.qdrant_cos_sync import (
    get_qdrant_cos_status,
    install_qdrant_from_cos,
    publish_qdrant_release_to_cos,
)
from services.utils import tencent_cos_client
from services.utils.backup_scheduler import (
    BACKUP_HOUR,
    BACKUP_RETENTION_COUNT,
    get_backup_status,
    get_next_backup_time,
    list_cos_backups,
    run_backup_now,
)


def _serialize_cos_backup(entry: Dict[str, Any]) -> Dict[str, Any]:
    last_mod = tencent_cos_client.parse_cos_timestamp(entry.get("last_modified"))
    manifest_key = f"{entry['key']}.manifest.json"
    return {
        "key": entry.get("key"),
        "filename": entry.get("filename") or entry.get("key", "").rsplit("/", 1)[-1],
        "size_mb": round(int(entry.get("size", 0)) / (1024 * 1024), 2),
        "last_modified": last_mod.isoformat() if last_mod else None,
        "has_manifest": tencent_cos_client.object_exists(manifest_key),
    }


def get_cos_overview_status() -> Dict[str, Any]:
    """Overview payload for admin GET /cos/status."""
    connection = tencent_cos_client.test_cos_connection()
    crowdsec_meta = tencent_cos_client.get_json(crowdsec_meta_cos_key())
    abuseipdb_meta = tencent_cos_client.get_json(abuseipdb_meta_cos_key())
    geolite_meta = tencent_cos_client.get_json(geolite_meta_cos_key())
    qdrant_meta = tencent_cos_client.get_json(qdrant_meta_cos_key())
    celery_meta = tencent_cos_client.get_json(celery_meta_cos_key())
    local_backup = get_backup_status()
    cos_backups = list_cos_backups()

    def _artifact_health(present: bool) -> str:
        if not connection.get("configured"):
            return "disabled"
        if not connection.get("ok"):
            return "error"
        return "ok" if present else "missing"

    pg_latest = local_backup.get("cos", {}).get("latest")
    return {
        "connection": connection,
        "config": cos_config_snapshot(),
        "sync_role": cos_sync_role(),
        "schedule_hour": BACKUP_HOUR,
        "next_scheduled_run": get_next_backup_time().isoformat(),
        "retention": {
            "local_count": BACKUP_RETENTION_COUNT,
            "cos_days": 2,
        },
        "artifacts": {
            "database_backups": {
                "local_count": len(local_backup.get("backups") or []),
                "cos_count": len(cos_backups),
                "health": _artifact_health(len(cos_backups) > 0 or not local_backup.get("cos", {}).get("enabled")),
                "latest_cos": pg_latest,
            },
            "crowdsec": {
                "health": _artifact_health(crowdsec_meta is not None),
                "cos_meta": crowdsec_meta,
            },
            "abuseipdb": {
                "health": _artifact_health(abuseipdb_meta is not None),
                "cos_meta": abuseipdb_meta,
            },
            "geolite": {
                "health": _artifact_health(geolite_meta is not None),
                "cos_meta": geolite_meta,
            },
            "qdrant": {
                "health": _artifact_health(qdrant_meta is not None),
                "cos_meta": qdrant_meta,
            },
            "celery": {
                "health": _artifact_health(celery_meta is not None),
                "cos_meta": celery_meta,
            },
        },
    }


def get_cos_backups_payload() -> Dict[str, Any]:
    """Local + COS backup lists for admin panel."""
    local = get_backup_status()
    cos_items = [_serialize_cos_backup(item) for item in list_cos_backups()]
    cos_items.sort(key=lambda row: row.get("last_modified") or "", reverse=True)
    return {
        "local": local,
        "cos": {
            "enabled": local.get("cos", {}).get("enabled", False),
            "count": len(cos_items),
            "backups": cos_items,
        },
    }


async def trigger_backup_now_admin() -> Dict[str, Any]:
    """Manual backup trigger."""
    ok = await run_backup_now()
    return {"ok": ok}


async def trigger_crowdsec_sync_admin() -> Dict[str, Any]:
    """Role-aware CrowdSec sync."""
    result = await merge_crowdsec_blocklist_for_role(force=True)
    return result


async def trigger_abuseipdb_sync_admin() -> Dict[str, Any]:
    """Role-aware AbuseIPDB sync (API+upload or COS pull)."""
    return await sync_blacklist_for_role(force=True, force_crowdsec_merge=True)


async def get_abuseipdb_status_admin() -> Dict[str, Any]:
    """AbuseIPDB COS status."""
    return await get_abuseipdb_cos_status()


async def trigger_geolite_sync_admin() -> Dict[str, Any]:
    """Role-aware GeoLite publish or install."""
    return await sync_geolite_for_role(force=True)


async def get_geolite_status_admin() -> Dict[str, Any]:
    """GeoLite COS status."""
    return await get_geolite_cos_status()


async def trigger_qdrant_publish_admin() -> Dict[str, Any]:
    """Publisher: upload Qdrant release to COS."""
    return await publish_qdrant_release_to_cos(force=True)


async def trigger_qdrant_install_admin() -> Dict[str, Any]:
    """Consumer: install Qdrant from COS."""
    return await install_qdrant_from_cos(force=True)


async def get_crowdsec_status_admin() -> Dict[str, Any]:
    """CrowdSec COS status."""
    return await get_crowdsec_cos_status()


async def get_qdrant_status_admin() -> Dict[str, Any]:
    """Qdrant COS status."""
    return await get_qdrant_cos_status()


async def trigger_celery_publish_admin() -> Dict[str, Any]:
    """Publisher: upload Celery wheel to COS."""
    return await publish_celery_release_to_cos(force=True)


async def trigger_celery_install_admin() -> Dict[str, Any]:
    """Consumer: install Celery from COS."""
    return await install_celery_from_cos(force=True)


async def get_celery_status_admin() -> Dict[str, Any]:
    """Celery COS status."""
    return await get_celery_cos_status()
