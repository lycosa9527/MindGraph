"""Repository for ZhiHui conversations and generation history."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Optional, Sequence

from sqlalchemy import desc, func, select
from sqlalchemy.orm import selectinload

from models.domain.zhihui import ZhihuiConversation, ZhihuiGeneration, generate_zhihui_id
from repositories.base import BaseRepository

_ACTIVE_STATUSES = ("queued", "planning", "generating")
_DEFAULT_STALE_MINUTES = 60
_MAX_ACTIVE_DIAGRAM_JOBS = 2


class ZhihuiGenerationRepository(BaseRepository[ZhihuiGeneration]):
    """Async CRUD for zhihui_generations."""

    model = ZhihuiGeneration

    async def get_by_uuid(self, generation_id: str) -> Optional[ZhihuiGeneration]:
        """Load one generation by UUID primary key."""
        return await self.session.get(ZhihuiGeneration, generation_id)

    async def list_by_conversation(self, conversation_id: str) -> Sequence[ZhihuiGeneration]:
        """Ordered slides/images for one conversation."""
        stmt = (
            select(ZhihuiGeneration)
            .where(ZhihuiGeneration.conversation_id == conversation_id)
            .order_by(
                ZhihuiGeneration.slide_index.asc().nulls_last(),
                ZhihuiGeneration.created_at.asc(),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def cover_and_counts(
        self,
        conversation_ids: Sequence[str],
    ) -> dict[str, tuple[Optional[str], int]]:
        """
        One-query cover key + slide count per conversation.

        Returns ``{conversation_id: (cover_cos_key, slide_count)}``.
        """
        ids = [cid for cid in conversation_ids if cid]
        if not ids:
            return {}
        stmt = (
            select(
                ZhihuiGeneration.conversation_id,
                ZhihuiGeneration.cos_logical_key,
                ZhihuiGeneration.slide_index,
                ZhihuiGeneration.created_at,
            )
            .where(ZhihuiGeneration.conversation_id.in_(ids))
            .order_by(
                ZhihuiGeneration.conversation_id.asc(),
                ZhihuiGeneration.slide_index.asc().nulls_last(),
                ZhihuiGeneration.created_at.asc(),
            )
        )
        result = await self.session.execute(stmt)
        out: dict[str, tuple[Optional[str], int]] = {cid: (None, 0) for cid in ids}
        for conversation_id, cos_key, _slide_index, _created in result.all():
            if conversation_id is None:
                continue
            cover, count = out.get(conversation_id, (None, 0))
            if count == 0:
                cover = cos_key
            out[conversation_id] = (cover, count + 1)
        return out

    async def create_generation(
        self,
        *,
        generation_id: str,
        prompt: str,
        cos_logical_key: str,
        language: str = "zh",
        enhanced_prompt: Optional[str] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        conversation_id: Optional[str] = None,
        dify_conversation_id: Optional[str] = None,
        dify_user_id: Optional[str] = None,
        content_type: str = "image/jpeg",
        size: Optional[str] = None,
        api_key_id: Optional[int] = None,
        slide_index: Optional[int] = None,
        slide_title: Optional[str] = None,
        teacher_script: Optional[str] = None,
        focus_node_ids: Optional[list[Any]] = None,
        commit: bool = True,
    ) -> ZhihuiGeneration:
        """Insert a generation history row."""
        row = ZhihuiGeneration(
            id=generation_id,
            prompt=prompt,
            enhanced_prompt=enhanced_prompt,
            language=language,
            user_id=user_id,
            organization_id=organization_id,
            conversation_id=conversation_id,
            dify_conversation_id=dify_conversation_id,
            dify_user_id=dify_user_id,
            cos_logical_key=cos_logical_key,
            content_type=content_type,
            size=size,
            api_key_id=api_key_id,
            slide_index=slide_index,
            slide_title=slide_title,
            teacher_script=teacher_script,
            focus_node_ids=focus_node_ids,
        )
        self.session.add(row)
        await self.session.flush()
        if commit:
            await self.session.commit()
            await self.session.refresh(row)
        return row

    async def delete_generation(self, generation_id: str, *, commit: bool = True) -> bool:
        """Delete a generation row by id. Returns True if a row was deleted."""
        row = await self.get_by_uuid(generation_id)
        if row is None:
            return False
        await self.session.delete(row)
        await self.session.flush()
        if commit:
            await self.session.commit()
        return True


class ZhihuiConversationRepository(BaseRepository[ZhihuiConversation]):
    """Async CRUD for zhihui_conversations."""

    model = ZhihuiConversation

    async def get_by_uuid(
        self,
        conversation_id: str,
        *,
        with_generations: bool = False,
    ) -> Optional[ZhihuiConversation]:
        """Load one conversation, optionally with ordered generations."""
        if not with_generations:
            return await self.session.get(ZhihuiConversation, conversation_id)
        stmt = (
            select(ZhihuiConversation)
            .where(ZhihuiConversation.id == conversation_id)
            .options(selectinload(ZhihuiConversation.generations))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_recent(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        user_id: Optional[int] = None,
        mode: Optional[str] = None,
    ) -> Sequence[ZhihuiConversation]:
        """Newest-updated conversations first."""
        stmt = select(ZhihuiConversation)
        if user_id is not None:
            stmt = stmt.where(ZhihuiConversation.user_id == user_id)
        if mode:
            stmt = stmt.where(ZhihuiConversation.mode == mode)
        stmt = stmt.order_by(desc(ZhihuiConversation.updated_at)).offset(max(0, offset)).limit(max(1, min(limit, 200)))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_latest_diagram_conversation(
        self,
        *,
        user_id: int,
        diagram_id: str,
    ) -> Optional[ZhihuiConversation]:
        """Newest diagram-mode conversation for one library mind map (owner-scoped)."""
        cleaned = (diagram_id or "").strip()
        if not cleaned:
            return None
        stmt = (
            select(ZhihuiConversation)
            .where(
                ZhihuiConversation.user_id == user_id,
                ZhihuiConversation.mode == "diagram",
                ZhihuiConversation.diagram_id == cleaned,
            )
            .order_by(desc(ZhihuiConversation.updated_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_conversations(self, *, user_id: Optional[int] = None, mode: Optional[str] = None) -> int:
        """Total conversation rows."""
        stmt = select(func.count()).select_from(ZhihuiConversation)
        if user_id is not None:
            stmt = stmt.where(ZhihuiConversation.user_id == user_id)
        if mode:
            stmt = stmt.where(ZhihuiConversation.mode == mode)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def count_active_diagram_jobs(self, user_id: int) -> int:
        """Count non-terminal diagram lesson jobs for concurrency gating."""
        stmt = (
            select(func.count())
            .select_from(ZhihuiConversation)
            .where(
                ZhihuiConversation.user_id == user_id,
                ZhihuiConversation.mode == "diagram",
                ZhihuiConversation.status.in_(_ACTIVE_STATUSES),
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def mark_stale_active_jobs(
        self,
        *,
        max_age_minutes: int = _DEFAULT_STALE_MINUTES,
        user_id: Optional[int] = None,
    ) -> tuple[int, list[str]]:
        """
        Mark long-stuck active jobs as failed/partial.

        Jobs with generations become ``partial``; others ``failed``.
        Returns ``(updated_count, celery_task_ids)`` for revoke.
        """
        cutoff = datetime.now(UTC) - timedelta(minutes=max(5, int(max_age_minutes)))
        stmt = select(ZhihuiConversation).where(
            ZhihuiConversation.status.in_(_ACTIVE_STATUSES),
            ZhihuiConversation.updated_at < cutoff,
        )
        if user_id is not None:
            stmt = stmt.where(ZhihuiConversation.user_id == user_id)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        if not rows:
            return 0, []
        gen_repo = ZhihuiGenerationRepository(self.session)
        updated = 0
        task_ids: list[str] = []
        for row in rows:
            gens = await gen_repo.list_by_conversation(row.id)
            row.status = "partial" if gens else "failed"
            row.error_message = (f"Timed out after {max_age_minutes} minutes without progress")[:2000]
            row.progress = {
                "phase": row.status,
                "slide_count": len(gens),
                "stale": True,
            }
            row.updated_at = datetime.now(UTC)
            if row.celery_task_id:
                task_ids.append(str(row.celery_task_id))
            updated += 1
        if updated:
            await self.session.commit()
        return updated, task_ids

    @staticmethod
    def max_active_diagram_jobs() -> int:
        """Per-user concurrent diagram-lesson cap."""
        return _MAX_ACTIVE_DIAGRAM_JOBS

    async def create_conversation(
        self,
        *,
        mode: str,
        title: str,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        diagram_id: Optional[str] = None,
        diagram_title: Optional[str] = None,
        style_seed: Optional[str] = None,
        planner_model: Optional[str] = None,
        image_model: Optional[str] = None,
        lesson_plan_json: Optional[dict[str, Any]] = None,
        status: str = "queued",
        progress: Optional[dict[str, Any]] = None,
        language: str = "zh",
        conversation_id: Optional[str] = None,
        commit: bool = True,
    ) -> ZhihuiConversation:
        """Insert a conversation row."""
        now = datetime.now(UTC)
        row = ZhihuiConversation(
            id=conversation_id or generate_zhihui_id(),
            user_id=user_id,
            organization_id=organization_id,
            mode=mode,
            title=(title or "")[:256],
            diagram_id=diagram_id,
            diagram_title=diagram_title,
            style_seed=style_seed,
            planner_model=planner_model,
            image_model=image_model,
            lesson_plan_json=lesson_plan_json,
            status=status,
            progress=progress,
            language=language,
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        await self.session.flush()
        if commit:
            await self.session.commit()
            await self.session.refresh(row)
        return row

    async def update_conversation(
        self,
        conversation_id: str,
        *,
        status: Optional[str] = None,
        progress: Optional[dict[str, Any]] = None,
        error_message: Optional[str] = None,
        style_seed: Optional[str] = None,
        lesson_plan_json: Optional[dict[str, Any]] = None,
        celery_task_id: Optional[str] = None,
        title: Optional[str] = None,
        clear_error: bool = False,
        commit: bool = True,
    ) -> Optional[ZhihuiConversation]:
        """Patch mutable conversation fields."""
        row = await self.get_by_uuid(conversation_id)
        if row is None:
            return None
        if status is not None:
            row.status = status
        if progress is not None:
            row.progress = progress
        if clear_error:
            row.error_message = None
        elif error_message is not None:
            row.error_message = error_message
        if style_seed is not None:
            row.style_seed = style_seed
        if lesson_plan_json is not None:
            row.lesson_plan_json = lesson_plan_json
        if celery_task_id is not None:
            row.celery_task_id = celery_task_id
        if title is not None:
            row.title = title[:256]
        row.updated_at = datetime.now(UTC)
        await self.session.flush()
        if commit:
            await self.session.commit()
            await self.session.refresh(row)
        return row

    async def claim_for_run(
        self,
        conversation_id: str,
        *,
        celery_task_id: Optional[str] = None,
    ) -> Optional[ZhihuiConversation]:
        """
        Claim a conversation for the lesson pipeline.

        ``queued`` → ``planning``. Resume statuses (``planning`` / ``generating`` /
        ``partial``) keep their status but refresh ``celery_task_id``.
        """
        row = await self.get_by_uuid(conversation_id)
        if row is None:
            return None
        if row.status in ("complete", "cancelled"):
            return row
        # Resume after transient failure / partial when a lesson plan was persisted.
        if row.status in ("failed", "partial"):
            if not isinstance(row.lesson_plan_json, dict):
                return row
            row.status = "generating"
            row.progress = {"phase": "generating", "resumed": True}
            row.error_message = None
        if celery_task_id:
            row.celery_task_id = celery_task_id
        if row.status == "queued":
            row.status = "planning"
            row.progress = {"phase": "planning"}
            row.error_message = None
        row.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def delete_conversation(self, conversation_id: str, *, commit: bool = True) -> bool:
        """Delete conversation and cascaded generations."""
        row = await self.get_by_uuid(conversation_id)
        if row is None:
            return False
        await self.session.delete(row)
        await self.session.flush()
        if commit:
            await self.session.commit()
        return True

    async def first_generation_key(self, conversation_id: str) -> Optional[str]:
        """COS key for cover thumbnail (first slide)."""
        stmt = (
            select(ZhihuiGeneration.cos_logical_key)
            .where(ZhihuiGeneration.conversation_id == conversation_id)
            .order_by(
                ZhihuiGeneration.slide_index.asc().nulls_last(),
                ZhihuiGeneration.created_at.asc(),
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
