"""Load a library diagram and store a rendered PNG as a 研习社 attachment.

Bytes go to COS (local disk only when COS is off). Compose inserts markdown
that points at ``/api/chat/attachments/{id}/download``; peers pull the same
URL and get a short-lived COS redirect.

Playwright capture stays in the route so this module never imports ``routers.api``.
"""

import logging
import re
from typing import Any, Dict, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from services.features.workshop_chat.file_service import FileService
from services.redis.cache.redis_diagram_cache import get_diagram_cache

logger = logging.getLogger(__name__)

_PNG_NAME_UNSAFE = re.compile(r"[^\w\-]+", flags=re.UNICODE)


def png_filename_from_title(title: str) -> str:
    """Build a short ``.png`` basename from a diagram title."""
    cleaned = _PNG_NAME_UNSAFE.sub("_", title.strip()).strip("_")
    base = (cleaned or "diagram")[:80]
    return f"{base}.png"


async def load_library_diagram_spec(
    user_id: int,
    diagram_id: str,
) -> Tuple[Dict[str, Any], str, str]:
    """Return ``(spec, diagram_type, title)`` for a library diagram the user owns.

    Raises ``LookupError`` when the diagram is missing, ``ValueError`` for a bad spec.
    """
    cache = get_diagram_cache()
    record = await cache.get_diagram(user_id, diagram_id)
    if not record:
        raise LookupError("Diagram not found")

    spec = record.get("spec") or {}
    if not isinstance(spec, dict):
        raise ValueError("Invalid diagram spec")

    diagram_type = str(record.get("diagram_type") or "bubble_map")
    title = str(record.get("title") or "diagram")
    return spec, diagram_type, title


async def store_library_diagram_png(
    db: AsyncSession,
    user_id: int,
    title: str,
    png_bytes: bytes,
    diagram_id: str,
) -> Dict[str, Any]:
    """Persist a rendered PNG as a draft chat attachment."""
    if not png_bytes or len(png_bytes) < 64:
        logger.warning("[WorkshopDiagram] empty PNG for diagram %s", diagram_id)
        raise RuntimeError("Failed to render diagram PNG")

    return await FileService.save_png_bytes(
        db,
        uploader_id=user_id,
        data=png_bytes,
        filename=png_filename_from_title(title),
    )
