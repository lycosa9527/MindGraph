"""Repository for durable generate_dingtalk preview metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.domain.generation_preview_link import GenerationPreviewLink


class GenerationPreviewLinkRepository:
    """PostgreSQL persistence for preview id lookups."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def upsert_outcome(
        self,
        preview_id: str,
        *,
        skip_reason: str,
        language: str,
        diagram_id: Optional[str] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        diagram_type: str = "",
        title: str = "",
        spec: Optional[dict[str, Any]] = None,
    ) -> None:
        """Insert or update preview metadata keyed by temp PNG id."""
        pid = (preview_id or "").strip()[:8]
        if not pid:
            return
        now = datetime.now(UTC)
        values = {
            "preview_id": pid,
            "skip_reason": (skip_reason or "").strip()[:64],
            "language": (language or "zh").strip()[:16] or "zh",
            "diagram_id": (diagram_id or "").strip()[:36] or None,
            "user_id": user_id if user_id is not None and user_id > 0 else None,
            "organization_id": organization_id if organization_id is not None else None,
            "diagram_type": (diagram_type or "mind_map").strip()[:64] or "mind_map",
            "title": (title or "Diagram").strip()[:200] or "Diagram",
            "spec": spec if isinstance(spec, dict) and spec else None,
            "updated_at": now,
        }
        stmt = pg_insert(GenerationPreviewLink).values(**values, created_at=now)
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            index_elements=[GenerationPreviewLink.preview_id],
            set_={
                "skip_reason": excluded.skip_reason,
                "language": excluded.language,
                "diagram_id": excluded.diagram_id,
                "user_id": excluded.user_id,
                "organization_id": excluded.organization_id,
                "diagram_type": excluded.diagram_type,
                "title": excluded.title,
                "spec": excluded.spec,
                "updated_at": excluded.updated_at,
            },
        )
        await self._db.execute(stmt)
        await self._db.commit()

    async def get_by_preview_id(self, preview_id: str) -> Optional[GenerationPreviewLink]:
        """Return durable preview row or None."""
        pid = (preview_id or "").strip()[:8]
        if not pid:
            return None
        stmt = select(GenerationPreviewLink).where(GenerationPreviewLink.preview_id == pid).limit(1)
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def set_diagram_id(self, preview_id: str, diagram_id: str) -> bool:
        """Attach a library diagram uuid after reclaim or late save."""
        row = await self.get_by_preview_id(preview_id)
        if row is None:
            return False
        row.diagram_id = (diagram_id or "").strip()[:36] or None
        row.skip_reason = ""
        row.spec = None
        row.updated_at = datetime.now(UTC)
        await self._db.commit()
        return True
