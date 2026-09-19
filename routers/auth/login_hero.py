"""Public /auth cinematic hero: COS 302 or local silent MP4."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, RedirectResponse

from services.auth.login_hero_clips import LOGIN_HERO_CONTENT_TYPE, parse_hero_clip_id
from services.auth.login_hero_media import HERO_CACHE, hero_presigned_url, local_hero_path

router = APIRouter()


@router.get("/login-hero/{clip_file}")
async def serve_login_hero(clip_file: str):
    """Redirect the browser to a looping login clip. No login required."""
    try:
        clip_id = parse_hero_clip_id(clip_file)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
    url = hero_presigned_url(clip_id)
    if url:
        return RedirectResponse(url, status_code=302, headers=HERO_CACHE)
    path = local_hero_path(clip_id)
    if path is not None:
        return FileResponse(path, media_type=LOGIN_HERO_CONTENT_TYPE, headers=HERO_CACHE)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
