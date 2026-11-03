"""
Daily PostgreSQL backup mirror on Aliyun OSS.

Runs beside the Tencent COS upload. Each store has its own flag, so a failure
on one still leaves the other copy in place. Retention matches COS: drop dumps
older than two days, and delete the companion manifest with the dump.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.utils import aliyun_oss_client

logger = logging.getLogger(__name__)

_DUMP_MARKER = "mindgraph.postgresql."


def oss_backup_enabled() -> bool:
    """True when OSS_BACKUP_ENABLED is set."""
    return os.getenv("OSS_BACKUP_ENABLED", "false").lower() == "true"


def upload_backup_to_oss(backup_path: Path, max_retries: int = 3) -> bool:
    """Upload one backup file under OSS_KEY_PREFIX."""
    if not oss_backup_enabled():
        logger.debug("[Backup] OSS backup disabled, skipping upload")
        return True
    if not backup_path.is_file():
        logger.error("[Backup] Backup file does not exist: %s", backup_path)
        return False
    if not aliyun_oss_client.oss_credentials_configured():
        logger.warning(
            "[Backup] OSS backup enabled but credentials are missing "
            "(OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET / OSS_BUCKET), skipping upload"
        )
        return False
    try:
        file_size = backup_path.stat().st_size
    except OSError as exc:
        logger.error("[Backup] Cannot access backup file %s: %s", backup_path, exc)
        return False
    if file_size == 0:
        logger.error("[Backup] Backup file is empty: %s", backup_path)
        return False
    object_key = aliyun_oss_client.oss_object_key(backup_path.name)
    return aliyun_oss_client.upload_file(
        backup_path,
        object_key,
        max_retries=max_retries,
        log_prefix="[Backup]",
    )


def list_oss_backups() -> List[Dict[str, Any]]:
    """List PostgreSQL dumps under the OSS backup prefix."""
    if not oss_backup_enabled() or not aliyun_oss_client.oss_credentials_configured():
        return []
    prefix = aliyun_oss_client.normalized_oss_prefix()
    objects = aliyun_oss_client.list_prefix(
        prefix,
        suffix_filter=".dump",
        contains_filter=_DUMP_MARKER,
    )
    backups: List[Dict[str, Any]] = []
    for obj in objects:
        backups.append(
            {
                "key": obj["key"],
                "size": obj["size"],
                "last_modified": obj["last_modified"],
                "filename": obj["filename"],
            }
        )
    logger.debug("[Backup] Found %s backup(s) in OSS", len(backups))
    return backups


def cleanup_old_oss_backups(retention_days: int = 2) -> int:
    """Delete OSS dumps, and their manifests, older than retention_days."""
    if not oss_backup_enabled() or not aliyun_oss_client.oss_credentials_configured():
        return 0
    backups = list_oss_backups()
    if not backups:
        logger.debug("[Backup] No OSS backups found with prefix: %s", aliyun_oss_client.normalized_oss_prefix())
        return 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(days=retention_days)
    deleted = 0
    for backup in backups:
        last_modified = backup.get("last_modified")
        if not isinstance(last_modified, datetime) or last_modified >= cutoff:
            continue
        age_days = (now - last_modified).days
        logger.info(
            "[Backup] Deleting old OSS backup: %s (age: %s days)",
            backup["key"],
            age_days,
        )
        if not aliyun_oss_client.delete_object(str(backup["key"]), log_prefix="[Backup]"):
            continue
        deleted += 1
        manifest_key = f"{backup['key']}.manifest.json"
        aliyun_oss_client.delete_object(manifest_key, log_prefix="[Backup]")
    if deleted > 0:
        logger.info("[Backup] Deleted %s old backup(s) from OSS", deleted)
    return deleted


def upload_oss_backup_if_enabled(backup_path: Path, manifest_path: Optional[Path]) -> None:
    """Upload the dump and manifest, then apply the two-day retention."""
    if not oss_backup_enabled():
        logger.debug("[Backup] OSS backup disabled (OSS_BACKUP_ENABLED=false), skipping upload")
        return
    logger.info("[Backup] OSS backup enabled, starting upload...")
    logger.info(
        "[Backup] OSS config: bucket=%s, region=%s, prefix=%s",
        aliyun_oss_client.oss_bucket_name(),
        aliyun_oss_client.oss_region(),
        aliyun_oss_client.normalized_oss_prefix(),
    )
    if not upload_backup_to_oss(backup_path):
        logger.error("[Backup] OSS upload failed, but local backup succeeded")
        return
    logger.info("[Backup] OSS dump upload completed successfully")
    if manifest_path and manifest_path.is_file():
        if upload_backup_to_oss(manifest_path):
            logger.info("[Backup] OSS manifest upload completed")
        else:
            logger.warning("[Backup] OSS manifest upload failed")
    deleted = cleanup_old_oss_backups(retention_days=2)
    if deleted > 0:
        logger.info("[Backup] Cleaned up %s old backup(s) from OSS", deleted)


def oss_backup_summary() -> Dict[str, Any]:
    """Status block for get_backup_status."""
    summary: Dict[str, Any] = {
        "enabled": oss_backup_enabled(),
        "configured": aliyun_oss_client.oss_credentials_configured(),
        "bucket": aliyun_oss_client.oss_bucket_name() or None,
        "prefix": aliyun_oss_client.normalized_oss_prefix() or None,
        "count": 0,
        "latest": None,
    }
    if not summary["enabled"] or not summary["configured"]:
        return summary
    items = list_oss_backups()
    summary["count"] = len(items)
    if not items:
        return summary
    latest = max(items, key=lambda item: item.get("last_modified") or datetime.min)
    last_mod = latest.get("last_modified")
    summary["latest"] = {
        "key": latest.get("key"),
        "filename": latest.get("filename") or str(latest.get("key", "")).rsplit("/", 1)[-1],
        "size_mb": round(int(latest.get("size", 0)) / (1024 * 1024), 2),
        "last_modified": last_mod.isoformat() if isinstance(last_mod, datetime) else None,
    }
    return summary
