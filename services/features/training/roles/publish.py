"""Publish packed role WebPs to every non-prod training COS prefix."""

from __future__ import annotations

import asyncio
import logging

from config.cos_env_prefix import (
    cos_production_tree_enabled,
    uses_live_production_prefixes,
)
from config.settings import config
from services.features.training.roles.catalog import (
    ROLE_CONTENT_TYPE,
    packed_role_file,
    packed_role_filenames,
    parse_packed_role_key,
)
from services.features.training.storage.backend import cos_training_enabled
from services.features.training.training_logger import log_training
from services.utils.tencent_cos_client import cos_object_key, head_object, upload_bytes

logger = logging.getLogger(__name__)

# Black-cat mascots are shared catalog assets, not per-course media.
_SHARED_ROLE_ENV_ROOTS = ("dev", "test")


class _RolePublishHolder:
    """Remember a successful catalog publish without a global statement."""

    def __init__(self) -> None:
        self.done = False
        self.lock = asyncio.Lock()


_HOLDER = _RolePublishHolder()


def packed_role_cos_prefixes() -> tuple[str, ...]:
    """Dev and test catalog only. Production never writes roles (no ``production/``)."""
    current = (config.COS_TRAINING_PREFIX or "").strip().rstrip("/")
    if current.startswith("production/") or uses_live_production_prefixes() or cos_production_tree_enabled():
        return ()
    prefixes: list[str] = [f"{root}/training" for root in _SHARED_ROLE_ENV_ROOTS]
    if current and current not in prefixes:
        prefixes.append(current)
    return tuple(prefixes)


def _object_matches(object_key: str, local_size: int) -> bool:
    meta = head_object(object_key)
    if not meta:
        return False
    remote = meta.get("ContentLength")
    if remote is None:
        remote = meta.get("Content-Length")
    return int(remote or 0) == local_size


def publish_packed_roles_sync() -> bool:
    """Upload missing or size-mismatched role objects to every shared env prefix."""
    if not cos_training_enabled():
        return True
    ok = True
    uploaded_count = 0
    skipped = 0
    failed = 0
    prefixes = packed_role_cos_prefixes()
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
        data = local.read_bytes()
        for prefix in prefixes:
            object_key = cos_object_key(logical_key, prefix=prefix)
            if _object_matches(object_key, size):
                skipped += 1
                continue
            uploaded = upload_bytes(
                data,
                object_key,
                content_type=ROLE_CONTENT_TYPE,
                log_prefix="[Training/COS]",
            )
            if not uploaded:
                logger.error(
                    "[Training/COS] packed role upload failed prefix=%s file=%s",
                    prefix,
                    filename,
                )
                ok = False
                failed += 1
                continue
            uploaded_count += 1
    log_training(
        logger,
        "packed_roles_publish",
        prefix="[Training/COS]",
        prefixes=list(prefixes),
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
