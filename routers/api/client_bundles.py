"""On-demand zip downloads for OpenClaw skill folder and Chrome extension.

Tier-gated for school lite organizations; requires authenticated session.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from models.domain.auth import User
from models.domain.messages import Language
from routers.auth.dependencies import get_language_dependency
from utils.auth import get_current_user
from utils.auth.school_tier import (
    TIER_FEATURE_API_TOKEN,
    TIER_FEATURE_CHROME_EXTENSION,
    assert_user_has_school_tier_feature,
)
from utils.db.session_open import actor_rls_session
from utils.extension_store_packaging import build_store_zip_bytes

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_OPENCLAW_SKILL_DIR = _PROJECT_ROOT / "openclaw" / "skills" / "mindgraph"
_FILE_READER_DIR = _PROJECT_ROOT / "clients" / "file-reader"
_FILE_READER_EXE = _FILE_READER_DIR / "dist" / "mindgraph-file-reader.exe"
_FILE_READER_ZIP = _PROJECT_ROOT / "frontend" / "public" / "downloads" / "mindgraph-file-reader.zip"
# Legacy names kept for backward-compatible download requests.
_LEGACY_FILE_READER_ZIP = _PROJECT_ROOT / "frontend" / "public" / "downloads" / "mindgraph-chat-reader.zip"


def _should_skip_path(relative: Path) -> bool:
    """Should skip path."""
    parts = relative.parts
    if "__pycache__" in parts:
        return True
    return any(p.startswith(".") for p in parts)


def _zip_directory(source_dir: Path, arc_root_name: str) -> bytes:
    """Zip directory."""
    if not source_dir.is_dir():
        raise FileNotFoundError(str(source_dir))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in source_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                rel = path.relative_to(source_dir)
            except ValueError:
                continue
            if _should_skip_path(rel):
                continue
            arcname = f"{arc_root_name}/{rel.as_posix()}"
            zf.write(path, arcname=arcname)
    return buffer.getvalue()


def _bundle_response(data: bytes, filename: str) -> Response:
    """Bundle response."""
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


@router.get("/downloads/mindgraph-openclaw-skill")
async def download_openclaw_skill_zip(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> Response:
    """Zip of `openclaw/skills/mindgraph` for OpenClaw / WorkBuddy."""
    async with actor_rls_session(current_user) as db:
        await assert_user_has_school_tier_feature(
            db,
            current_user,
            TIER_FEATURE_API_TOKEN,
            lang,
        )
    try:
        data = _zip_directory(_OPENCLAW_SKILL_DIR, "mindgraph")
    except FileNotFoundError:
        logger.warning("[ClientBundles] OpenClaw skill dir missing: %s", _OPENCLAW_SKILL_DIR)
        raise HTTPException(status_code=404, detail="OpenClaw skill bundle not available on this server") from None
    return _bundle_response(data, "mindgraph-openclaw-skill.zip")


@router.get("/downloads/mindgraph-chrome-extension")
async def download_chrome_extension_zip(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> Response:
    """Store-ready zip (manifest at root) for Chrome, Edge, or Partner Center upload."""
    async with actor_rls_session(current_user) as db:
        await assert_user_has_school_tier_feature(
            db,
            current_user,
            TIER_FEATURE_CHROME_EXTENSION,
            lang,
        )
    try:
        data = build_store_zip_bytes()
    except (FileNotFoundError, RuntimeError) as exc:
        logger.warning("[ClientBundles] Chrome extension store zip failed: %s", exc)
        raise HTTPException(
            status_code=404,
            detail="Chrome extension bundle not available on this server",
        ) from None
    return _bundle_response(data, "mindgraph-chrome-extension.zip")


@router.get("/downloads/mindgraph-extension")
async def download_extension_zip(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> Response:
    """Alias for mindgraph-chrome-extension (same store-ready zip)."""
    return await download_chrome_extension_zip(current_user=current_user, lang=lang)


@router.get("/downloads/mindgraph-file-reader")
async def download_file_reader_zip(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> Response:
    """Zip of the Windows file-reader helper for Document Summary chat ingest."""
    async with actor_rls_session(current_user) as db:
        await assert_user_has_school_tier_feature(
            db,
            current_user,
            TIER_FEATURE_API_TOKEN,
            lang,
        )
    if _FILE_READER_ZIP.is_file():
        return _bundle_response(_FILE_READER_ZIP.read_bytes(), "mindgraph-file-reader.zip")
    if _LEGACY_FILE_READER_ZIP.is_file():
        return _bundle_response(_LEGACY_FILE_READER_ZIP.read_bytes(), "mindgraph-file-reader.zip")
    if _FILE_READER_EXE.is_file():
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(_FILE_READER_EXE, arcname="mindgraph-file-reader.exe")
            readme = _FILE_READER_DIR / "README.md"
            if readme.is_file():
                zf.write(readme, arcname="README.md")
        return _bundle_response(buffer.getvalue(), "mindgraph-file-reader.zip")
    try:
        data = _zip_directory(_FILE_READER_DIR / "file_reader", "file_reader")
    except FileNotFoundError:
        logger.warning("[ClientBundles] File reader dir missing: %s", _FILE_READER_DIR)
        raise HTTPException(status_code=404, detail="File reader bundle not available on this server") from None
    return _bundle_response(data, "mindgraph-file-reader-source.zip")


@router.get("/downloads/mindgraph-chat-reader")
async def download_file_reader_zip_legacy(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> Response:
    """Backward-compatible alias for mindgraph-file-reader download."""
    return await download_file_reader_zip(current_user=current_user, lang=lang)
