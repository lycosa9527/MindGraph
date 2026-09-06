"""Publish packed role WebPs to the training COS prefix when missing."""

from __future__ import annotations

import asyncio
import logging

from services.features.training.roles.catalog import (
    ROLE_CONTENT_TYPE,
    packed_role_file,
    packed_role_filenames,
    parse_packed_role_key,
)
from services.features.training.storage.backend import cos_training_enabled
from services.features.training.storage.keys import full_cos_key
from services.features.training.training_logger import log_training
from services.utils.tencent_cos_client import head_object, upload_bytes

logger = logging.getLogger(__name__)


class _RolePublishHolder:
    """Remember a successful catalog publish without a global statement."""

    def __init__(self) -> None:
        self.done = False
        self.lock = asyncio.Lock()


_HOLDER = _RolePublishHolder()


def _object_matches(logical_key: str, local_size: int) -> bool:
    meta = head_object(full_cos_key(logical_key))
    if not meta:
        return False
    return int(meta.get("ContentLength") or 0) == local_size


def publish_packed_roles_sync() -> bool:
    """Upload any missing or size-mismatched packed role objects."""
    if not cos_training_enabled():
        return True
    ok = True
    uploaded_count = 0
    skipped = 0
    failed = 0
    for filename in packed_role_filenames():
        parsed = parse_packed_role_key(f"roles/{filename}")
        if parsed is None:
            ok = False
            failed += 1
            continue
        role_id, thumb = parsed
        local = packed_role_file(role_id, thumb=thumb)
        if local is None:
            logger.warning("[Training/COS] packed role missing on disk: %s", filename)
            ok = False
            failed += 1
            continue
        logical_key = f"roles/{filename}"
        size = local.stat().st_size
        if _object_matches(logical_key, size):
            skipped += 1
            continue
        uploaded = upload_bytes(
            local.read_bytes(),
            full_cos_key(logical_key),
            content_type=ROLE_CONTENT_TYPE,
            log_prefix="[Training/COS]",
        )
        if not uploaded:
            logger.error("[Training/COS] packed role upload failed: %s", filename)
            ok = False
            failed += 1
            continue
        uploaded_count += 1
    log_training(
        logger,
        "packed_roles_publish",
        prefix="[Training/COS]",
        uploaded=uploaded_count,
        skipped=skipped,
        failed=failed,
    )
    return ok


async def ensure_packed_roles_on_cos() -> None:
    """Idempotent first-use publish so live teachers hit COS, not the app."""
    if not cos_training_enabled() or _HOLDER.done:
        return
    async with _HOLDER.lock:
        if _HOLDER.done:
            return
        published = await asyncio.to_thread(publish_packed_roles_sync)
        if published:
            _HOLDER.done = True
