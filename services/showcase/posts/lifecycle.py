"""Showcase post lifecycle helpers (create rollback, withdraw/delete assets)."""

from __future__ import annotations

from typing import Any, Optional

from services.showcase.infra.observability import showcase_wf_log
from services.showcase.storage import delete_post_assets, storage_backend


async def rollback_created_post_assets(
    *,
    post_id: str,
    thumbnail_path: Optional[str] = None,
    spec: Optional[dict[str, Any]] = None,
    user_id: Optional[int] = None,
    reason: str = "create_fail",
) -> int:
    """Delete assets after a failed create commit; return deleted count."""
    showcase_wf_log(
        "create_rollback",
        reason,
        post_id=post_id,
        user_id=user_id,
        backend=storage_backend(),
    )
    return await delete_post_assets(
        post_id=post_id,
        thumbnail_path=thumbnail_path,
        spec=spec,
    )


def log_create_success(
    *,
    post_id: str,
    user_id: int,
    case_type: str,
) -> None:
    """Workflow log for successful create."""
    showcase_wf_log(
        "create",
        f"case_type={case_type}",
        post_id=post_id,
        user_id=user_id,
        backend=storage_backend(),
    )


def log_withdraw(
    *,
    post_id: str,
    user_id: int,
    reason: str = "hard_delete",
) -> None:
    """Workflow log for author withdraw (optional client-reported reason)."""
    detail = reason.strip() if reason and reason.strip() else "hard_delete"
    stage = "upload_rollback" if detail.startswith("upload_") else "withdraw"
    showcase_wf_log(
        stage,
        detail,
        post_id=post_id,
        user_id=user_id,
        backend=storage_backend(),
    )


def log_delete(
    *,
    post_id: str,
    user_id: int,
) -> None:
    """Workflow log for staff delete."""
    showcase_wf_log(
        "delete",
        "hard_delete",
        post_id=post_id,
        user_id=user_id,
        backend=storage_backend(),
    )


def log_cache_invalidate(*, post_id: str) -> None:
    """Workflow log for list/meta cache invalidation."""
    showcase_wf_log("cache_invalidate", "", post_id=post_id)
