"""Collect Showcase media keys from Postgres and COS."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import config
from models.domain.showcase import ShowcasePost
from services.showcase.storage.keys import (
    LEGACY_LOGICAL_PREFIX,
    LOGICAL_PREFIX,
    collect_keys_from_post,
    full_cos_key,
    logical_key_from_full_cos_key,
)
from services.utils import tencent_cos_client
from services.utils.tencent_cos_client import list_prefix


async def collect_db_logical_keys(db: AsyncSession) -> set[str]:
    """All media keys referenced by Showcase posts in Postgres."""
    rows = (await db.execute(select(ShowcasePost.thumbnail_path, ShowcasePost.spec))).all()
    keys: set[str] = set()
    for thumbnail_path, spec in rows:
        thumb = thumbnail_path if isinstance(thumbnail_path, str) else None
        spec_obj = spec if isinstance(spec, dict) else None
        for key in collect_keys_from_post(thumbnail_path=thumb, spec=spec_obj):
            if key:
                keys.add(key.lstrip("/").replace("\\", "/"))
    return keys


def list_cos_logical_keys() -> set[str]:
    """List objects under the Showcase COS prefix as logical keys."""
    prefix = full_cos_key(f"{LOGICAL_PREFIX}/")
    keys: set[str] = set()
    for entry in list_prefix(prefix):
        raw = entry.get("key")
        if not isinstance(raw, str) or not raw or raw.endswith("/"):
            continue
        logical = logical_key_from_full_cos_key(raw)
        keys.add(logical)
    return keys


def split_legacy_local_keys(db_keys: set[str]) -> tuple[set[str], list[str]]:
    """Split DB keys into COS-tracked vs legacy local-only references."""
    legacy: list[str] = []
    tracked: set[str] = set()
    for key in db_keys:
        if key.startswith(f"{LEGACY_LOGICAL_PREFIX}/"):
            legacy.append(key)
        else:
            tracked.add(key)
    return tracked, sorted(legacy)


def storage_config_snapshot() -> dict[str, Any]:
    """Non-secret COS config snapshot for admin status."""
    return {
        "bucket": (tencent_cos_client.COS_BUCKET or "").strip(),
        "region": (tencent_cos_client.COS_REGION or "").strip(),
        "prefix": (config.COS_SHOWCASE_PREFIX or "").strip(),
        "logical_prefix": LOGICAL_PREFIX,
    }
