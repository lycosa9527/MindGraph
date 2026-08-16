"""Serve Mind Classroom slide images."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from routers.api.helpers import verify_signed_url
from routers.auth.dependencies import get_async_db_with_request_rls, get_current_user_optional
from services.mind_classroom.asset_access import resolve_classroom_asset_owner_id
from services.mind_classroom.storage import aiter_bytes, create_presigned_get
from services.mind_classroom.storage_keys import is_classroom_logical_key, resolve_local_safe
from services.utils.error_types import FILE_IO_ERRORS
from services.zhihui.storage.backend import cos_zhihui_enabled

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/assets/{asset_path:path}")
async def download_classroom_asset(
    asset_path: str,
    sig: Optional[str] = None,
    exp: Optional[int] = None,
    proxy: bool = Query(False),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
):
    """Serve a classroom slide or transcript. Signed query or owning JWT."""
    normalized = asset_path.lstrip("/").replace("\\", "/")
    if "?" in normalized:
        normalized = normalized.split("?", 1)[0]
    if not is_classroom_logical_key(normalized):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    signed_ok = bool(sig and exp and verify_signed_url(normalized, sig, exp))
    if not signed_ok:
        if current_user is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired image URL")
        owner_id = await resolve_classroom_asset_owner_id(db, normalized)
        if owner_id is None or owner_id != int(current_user.id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    filename = Path(normalized).name
    media_type, _ = mimetypes.guess_type(filename)
    is_markdown = normalized.endswith(".md")
    if is_markdown:
        media_type = "text/markdown; charset=utf-8"
    elif not media_type:
        media_type = "image/png"
    disposition = f'inline; filename="{filename}"'
    cache_control = "private, no-store" if is_markdown else "public, max-age=86400"

    if proxy or not cos_zhihui_enabled():
        if not cos_zhihui_enabled():
            try:
                path = resolve_local_safe(normalized)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
            if not path.is_file():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
            return FileResponse(
                path=str(path),
                media_type=media_type,
                filename=filename,
                headers={
                    "Cache-Control": cache_control,
                    "Content-Disposition": disposition,
                    "X-Content-Type-Options": "nosniff",
                },
            )

        async def _stream():
            async for chunk in aiter_bytes(normalized):
                yield chunk

        return StreamingResponse(
            _stream(),
            media_type=media_type,
            headers={
                "Cache-Control": cache_control,
                "Content-Disposition": disposition,
                "X-Content-Type-Options": "nosniff",
            },
        )

    url = create_presigned_get(normalized, filename=filename)
    if url:
        return RedirectResponse(
            url=url,
            status_code=status.HTTP_302_FOUND,
            headers={"Cache-Control": "private, no-store"},
        )
    try:
        body = b""
        async for chunk in aiter_bytes(normalized):
            body += chunk
        if not body:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        return Response(
            content=body,
            media_type=media_type,
            headers={
                "Cache-Control": cache_control,
                "Content-Disposition": disposition,
                "X-Content-Type-Options": "nosniff",
            },
        )
    except FILE_IO_ERRORS as exc:
        logger.warning("[MindClassroom] Asset read failed key=%s err=%s", normalized, exc)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
