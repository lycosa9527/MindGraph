"""Diagram async repository."""

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.domain.diagrams import Diagram
from models.domain.diagram_snapshots import DiagramSnapshot

from .base import BaseRepository


class DiagramRepository(BaseRepository[Diagram]):
    model = Diagram

    async def get_by_user(
        self,
        user_id: int,
        *,
        include_deleted: bool = False,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[Diagram]:
        conditions = [Diagram.user_id == user_id]
        if not include_deleted:
            conditions.append(~Diagram.is_deleted)
        result = await self.session.execute(
            select(Diagram).where(*conditions).order_by(Diagram.updated_at.desc()).offset(offset).limit(limit)
        )
        return result.scalars().all()

    async def get_with_user(self, diagram_id: int) -> Optional[Diagram]:
        result = await self.session.execute(
            select(Diagram).options(selectinload(Diagram.user)).where(Diagram.id == diagram_id)
        )
        return result.scalar_one_or_none()

    async def count_by_user(self, user_id: int, *, include_deleted: bool = False) -> int:
        conditions = [Diagram.user_id == user_id]
        if not include_deleted:
            conditions.append(~Diagram.is_deleted)
        result = await self.session.execute(select(func.count()).select_from(Diagram).where(*conditions))
        return result.scalar_one()

    async def get_by_workshop_code(self, code: str) -> Optional[Diagram]:
        result = await self.session.execute(
            select(Diagram).where(
                Diagram.workshop_code == code,
                ~Diagram.is_deleted,
            )
        )
        return result.scalar_one_or_none()


class DiagramSnapshotRepository(BaseRepository[DiagramSnapshot]):
    model = DiagramSnapshot

    async def list_for_diagram(self, diagram_id: int, *, limit: int = 20) -> Sequence[DiagramSnapshot]:
        result = await self.session.execute(
            select(DiagramSnapshot)
            .where(DiagramSnapshot.diagram_id == diagram_id)
            .order_by(DiagramSnapshot.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


def get_diagram_repo(session: AsyncSession) -> DiagramRepository:
    return DiagramRepository(session)


def get_snapshot_repo(session: AsyncSession) -> DiagramSnapshotRepository:
    return DiagramSnapshotRepository(session)
