"""
Serve mind-map PDF export fonts (COS-backed, local cache).

Browser loads ``/api/mindmap_export_fonts/{filename}`` — same-origin, no CDN.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from services.infrastructure.sync.mindmap_export_fonts_cos import (
    FONT_FILES,
    ensure_font_cached_from_cos,
    fonts_status_snapshot,
    is_allowed_mindmap_export_font,
)

router = APIRouter(tags=["mindmap-export-fonts"])


@router.get("/mindmap_export_fonts/status")
async def mindmap_export_fonts_status() -> dict:
    """Debug/status for export font availability (no secrets)."""
    return fonts_status_snapshot()


@router.get("/mindmap_export_fonts/{filename}")
async def mindmap_export_font_file(filename: str) -> FileResponse:
    """Stream a vendored/COS export font for PDF embedding."""
    if not is_allowed_mindmap_export_font(filename):
        raise HTTPException(
            status_code=404,
            detail=f"Unknown font. Allowed: {', '.join(FONT_FILES)}",
        )
    path = ensure_font_cached_from_cos(filename)
    if path is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Export font not available. Publish with "
                "`python scripts/db/publish_mindmap_export_fonts_to_cos.py` "
                "or place files under frontend/public/fonts/."
            ),
        )
    return FileResponse(
        path,
        media_type="font/ttf",
        filename=filename,
        headers={
            "Cache-Control": "public, max-age=604800",
        },
    )
