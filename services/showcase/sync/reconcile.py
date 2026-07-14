"""Reconcile Showcase Postgres keys with COS bucket contents."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from services.showcase.infra.observability import showcase_wf_log
from services.showcase.storage import (
    cos_showcase_enabled,
    delete_key_sync,
    is_scoped_post_object_key,
    storage_backend,
)
from services.showcase.sync.inventory import (
    collect_db_logical_keys,
    list_cos_logical_keys,
    split_legacy_local_keys,
    storage_config_snapshot,
)
from services.showcase.sync.report import (
    ShowcaseReconcileReport,
    ShowcaseStorageStatus,
    diff_key_sets,
)
from services.utils.tencent_cos_client import cos_credentials_configured, test_cos_connection


async def reconcile_showcase_storage(db: AsyncSession) -> ShowcaseReconcileReport:
    """
    Diff DB media keys vs COS objects under the Showcase prefix.

    Local-only mode returns DB keys as missing_in_cos when objects are not on COS
    (expected); orphan_cos is empty without COS listing.
    """
    backend = storage_backend()
    db_keys = await collect_db_logical_keys(db)
    tracked, legacy = split_legacy_local_keys(db_keys)

    if cos_showcase_enabled():
        cos_keys = list_cos_logical_keys()
        matched, orphan, missing, unscoped = diff_key_sets(
            db_logical_keys=tracked,
            cos_logical_keys=cos_keys,
            scoped_check=is_scoped_post_object_key,
        )
        report = ShowcaseReconcileReport(
            backend=backend,
            db_key_count=len(db_keys),
            cos_object_count=len(cos_keys),
            matched=matched,
            orphan_cos=orphan,
            missing_in_cos=missing,
            unscoped=unscoped,
            legacy_local=legacy,
        )
    else:
        report = ShowcaseReconcileReport(
            backend=backend,
            db_key_count=len(db_keys),
            cos_object_count=0,
            matched=[],
            orphan_cos=[],
            missing_in_cos=sorted(tracked),
            unscoped=[],
            legacy_local=legacy,
        )

    showcase_wf_log(
        "sync_scan",
        (
            f"db={report.db_key_count} cos={report.cos_object_count} "
            f"orphan={len(report.orphan_cos)} missing={len(report.missing_in_cos)}"
        ),
        backend=backend,
    )
    return report


def purge_orphan_cos_objects(
    orphan_logical_keys: list[str],
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Delete orphan COS objects (logical keys not referenced in DB).

    dry_run=True (default) only reports what would be deleted.
    """
    planned = list(orphan_logical_keys)
    deleted: list[str] = []
    failed: list[str] = []
    if not dry_run:
        for key in planned:
            try:
                if delete_key_sync(key):
                    deleted.append(key)
                else:
                    # Still try full COS key delete path via delete_key_sync
                    failed.append(key)
            except (OSError, RuntimeError, ValueError) as exc:
                failed.append(f"{key}:{type(exc).__name__}")

    showcase_wf_log(
        "sync_purge",
        f"dry_run={dry_run} planned={len(planned)} deleted={len(deleted)} failed={len(failed)}",
        backend=storage_backend(),
    )
    return {
        "dry_run": dry_run,
        "planned": planned,
        "planned_count": len(planned),
        "deleted": deleted,
        "deleted_count": len(deleted),
        "failed": failed,
        "failed_count": len(failed),
    }


async def purge_orphans_from_reconcile(
    db: AsyncSession,
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Run reconcile then purge orphan_cos entries."""
    report = await reconcile_showcase_storage(db)
    purge = purge_orphan_cos_objects(report.orphan_cos, dry_run=dry_run)
    return {
        "report": report.to_dict(),
        "purge": purge,
    }


def build_storage_status() -> ShowcaseStorageStatus:
    """Admin health snapshot (no secrets)."""
    snap = storage_config_snapshot()
    probe: dict[str, Any] = {"ok": False, "error": "cos_disabled"}
    if cos_showcase_enabled():
        probe = test_cos_connection()
    elif cos_credentials_configured():
        probe = test_cos_connection()
        if probe.get("ok"):
            probe = {**probe, "error": "showcase_cos_disabled"}
            probe["ok"] = False

    detail = ""
    if not probe.get("ok"):
        detail = str(probe.get("error") or "unavailable")

    return ShowcaseStorageStatus(
        backend=storage_backend(),
        cos_enabled=cos_showcase_enabled(),
        credentials_configured=cos_credentials_configured(),
        bucket=str(snap.get("bucket") or ""),
        region=str(snap.get("region") or ""),
        prefix=str(snap.get("prefix") or ""),
        connection_ok=bool(probe.get("ok")),
        connection_detail=detail,
    )


# Public API
__all__ = [
    "build_storage_status",
    "purge_orphan_cos_objects",
    "purge_orphans_from_reconcile",
    "reconcile_showcase_storage",
]
