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

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_OPENCLAW_SKILL_DIR = _PROJECT_ROOT / "openclaw" / "skills" / "mindgraph"
_CHROME_EXTENSION_DIR = _PROJECT_ROOT / "chrome-extension"


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
    """Zip of `chrome-extension` for Load unpacked (or inspection)."""
    async with actor_rls_session(current_user) as db:
        await assert_user_has_school_tier_feature(
            db,
            current_user,
            TIER_FEATURE_CHROME_EXTENSION,
            lang,
        )
    try:
        data = _zip_directory(_CHROME_EXTENSION_DIR, "chrome-extension")
    except FileNotFoundError:
        logger.warning("[ClientBundles] Chrome extension dir missing: %s", _CHROME_EXTENSION_DIR)
        raise HTTPException(status_code=404, detail="Chrome extension bundle not available on this server") from None
    return _bundle_response(data, "mindgraph-chrome-extension.zip")
