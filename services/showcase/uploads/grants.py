"""Upload grant wrappers around Redis Showcase cache."""

from __future__ import annotations

from typing import Any, Optional

from services.redis.cache import redis_showcase_cache as showcase_cache
from services.showcase.infra.observability import showcase_wf_log


async def save_upload_grant(
    *,
    user_id: int,
    post_id: str,
    role: str,
    logical_key: str,
    content_type: str,
    max_bytes: int,
    ttl_seconds: int,
) -> None:
    """Persist anti-swap upload grant."""
    await showcase_cache.save_upload_grant(
        user_id=user_id,
        post_id=post_id,
        role=role,
        logical_key=logical_key,
        content_type=content_type,
        max_bytes=max_bytes,
        ttl_seconds=ttl_seconds,
    )
    showcase_wf_log(
        "upload_grant_saved",
        f"ttl={ttl_seconds}",
        post_id=post_id,
        user_id=user_id,
        role=role,
        key=logical_key,
    )


async def pop_upload_grant(
    *,
    user_id: int,
    post_id: str,
    role: str,
) -> Optional[dict[str, Any]]:
    """Consume upload grant (one-shot)."""
    grant = await showcase_cache.pop_upload_grant(
        user_id=user_id,
        post_id=post_id,
        role=role,
    )
    if grant:
        showcase_wf_log(
            "upload_grant_consumed",
            "",
            post_id=post_id,
            user_id=user_id,
            role=role,
            key=str(grant.get("key") or ""),
        )
    return grant
