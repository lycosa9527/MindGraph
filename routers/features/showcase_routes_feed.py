"""Showcase routes: meta, listing, favorites, and authenticated asset download."""

from __future__ import annotations

import mimetypes
from pathlib import Path

import orjson
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.showcase import ShowcasePost
from routers.features.showcase_constants import (
    CASE_TYPES,
    DIAGRAM_TYPE_LABELS,
)
from routers.features.showcase_helpers import (
    post_id_from_showcase_asset_path,
    resolve_showcase_disk_path,
)
from routers.features.showcase_permissions import can_view_non_approved_post
from routers.features.showcase_routes_posts import list_posts
from services.showcase.field_options import load_meta_payload
from services.showcase.infra.observability import showcase_wf_log
from services.showcase.storage import (
    collect_keys_from_post,
    cos_showcase_enabled,
    create_presigned_get,
    get_bytes,
    is_showcase_logical_key,
    storage_backend,
)
from utils.auth import get_current_user

router = APIRouter()


def _key_belongs_to_post(post: ShowcasePost, logical_key: str) -> bool:
    """True if the requested key is referenced by the post (or is legacy/spec JSON)."""
    normalized = logical_key.lstrip("/").replace("\\", "/")
    keys = collect_keys_from_post(thumbnail_path=post.thumbnail_path, spec=post.spec)
    if normalized in keys:
        return True
    # Spec JSON is PG-backed; allow legacy/synthetic paths when post has spec
    if normalized in {
        f"case_square/{post.id}.json",
        f"showcase/posts/{post.id}/spec.json",
    }:
        return bool(post.spec)
    return False


@router.get("/assets/{asset_path:path}")
async def download_showcase_asset(
    asset_path: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Serve Showcase files with AuthZ.

    COS: 302 to short-TTL presigned GET. Local/legacy: FileResponse or bytes.
    API never embeds durable COS host URLs in JSON — only redirect Location.
    """
    normalized = asset_path.lstrip("/").replace("\\", "/")
    if not is_showcase_logical_key(normalized):
        # Backward compat: bare filenames under legacy case_square/
        if "/" not in normalized:
            normalized = f"case_square/{normalized}"
        elif not normalized.startswith("case_square/") and not normalized.startswith("showcase/posts/"):
            showcase_wf_log(
                "download_deny",
                "invalid_path",
                user_id=current_user.id,
                key=normalized,
            )
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    post_id = post_id_from_showcase_asset_path(normalized)
    if not post_id:
        showcase_wf_log(
            "download_deny",
            "no_post_id",
            user_id=current_user.id,
            key=normalized,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    post = (await db.execute(select(ShowcasePost).where(ShowcasePost.id == post_id))).scalar_one_or_none()
    if not post:
        showcase_wf_log(
            "download_deny",
            "post_missing",
            post_id=post_id,
            user_id=current_user.id,
            key=normalized,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if post.status != "approved" and not await can_view_non_approved_post(post, current_user, db):
        showcase_wf_log(
            "download_deny",
            "forbidden_status",
            post_id=post_id,
            user_id=current_user.id,
            key=normalized,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if not _key_belongs_to_post(post, normalized):
        showcase_wf_log(
            "download_deny",
            "key_not_member",
            post_id=post_id,
            user_id=current_user.id,
            key=normalized,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    filename = Path(normalized).name
    media_type, _ = mimetypes.guess_type(filename)
    disposition = f'inline; filename="{filename}"'

    # Legacy / local-only spec JSON: synthesize from Postgres
    if normalized.endswith(f"{post.id}.json") or normalized.endswith("/spec.json"):
        if post.spec and isinstance(post.spec, dict):
            showcase_wf_log(
                "download",
                "spec_json",
                post_id=post_id,
                user_id=current_user.id,
                key=normalized,
                backend=storage_backend(),
            )
            return Response(
                content=orjson.dumps(post.spec),
                media_type="application/json",
                headers={"Content-Disposition": disposition},
            )

    if cos_showcase_enabled() and normalized.startswith("showcase/posts/"):
        url = create_presigned_get(normalized, filename=filename)
        if url:
            showcase_wf_log(
                "download",
                "presign_redirect",
                post_id=post_id,
                user_id=current_user.id,
                key=normalized,
                backend="cos",
            )
            return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)

    # Local file path
    try:
        disk_path = resolve_showcase_disk_path(normalized)
        showcase_wf_log(
            "download",
            "local_file",
            post_id=post_id,
            user_id=current_user.id,
            key=normalized,
            backend="local",
        )
        return FileResponse(
            path=str(disk_path),
            filename=filename,
            media_type=media_type,
            headers={"Content-Disposition": disposition},
        )
    except HTTPException:
        pass

    data = await get_bytes(normalized)
    if data is None:
        showcase_wf_log(
            "download_deny",
            "bytes_missing",
            post_id=post_id,
            user_id=current_user.id,
            key=normalized,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    showcase_wf_log(
        "download",
        "bytes",
        post_id=post_id,
        user_id=current_user.id,
        key=normalized,
        backend=storage_backend(),
    )
    return Response(
        content=data,
        media_type=media_type or "application/octet-stream",
        headers={"Content-Disposition": disposition},
    )


@router.get("/meta")
async def get_meta(
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Filter enums for the Showcase UI."""
    meta = await load_meta_payload(db)
    return {
        **meta,
        "diagram_types": sorted(DIAGRAM_TYPE_LABELS - {"mindmap"}),
        "case_types": sorted(CASE_TYPES),
    }


@router.get("/favorites")
async def list_favorite_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """List approved posts favorited by the current user."""
    return await list_posts(
        case_type=None,
        expert_recommended=False,
        subject=None,
        grade=None,
        diagram_type=None,
        publish_source=None,
        sort="newest",
        search=None,
        status_filter=None,
        mine=False,
        favorited=True,
        page=page,
        page_size=page_size,
        current_user=current_user,
        db=db,
    )
