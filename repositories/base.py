"""Generic async CRUD repository base.

Provides reusable async operations for any SQLAlchemy model so that
domain repositories only need to declare model-specific queries.
"""

from typing import Any, Generic, Optional, Sequence, Type, TypeVar

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from models.domain.auth import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Thin async wrapper around common SQLAlchemy 2.0 operations."""

    model: Type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -- reads ---------------------------------------------------------------

    async def get_by_id(self, record_id: int) -> Optional[ModelT]:
        return await self.session.get(self.model, record_id)

    async def get_all(
        self,
        *,
        filters: Optional[list] = None,
        order_by: Optional[list] = None,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> Sequence[ModelT]:
        stmt = select(self.model)
        stmt = self._apply_filters(stmt, filters)
        if order_by is not None:
            stmt = stmt.order_by(*order_by)
        if offset:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count(self, *, filters: Optional[list] = None) -> int:
        stmt = select(func.count()).select_from(self.model)
        stmt = self._apply_filters(stmt, filters)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def exists(self, *filters: Any) -> bool:
        stmt = select(func.count()).select_from(self.model).where(*filters)
        result = await self.session.execute(stmt)
        return result.scalar_one() > 0

    # -- writes --------------------------------------------------------------

    async def create(self, obj: ModelT, *, flush: bool = False) -> ModelT:
        self.session.add(obj)
        if flush:
            await self.session.flush()
        else:
            await self.session.commit()
            await self.session.refresh(obj)
        return obj

    async def create_many(self, objects: Sequence[ModelT], *, flush: bool = False) -> Sequence[ModelT]:
        self.session.add_all(objects)
        if flush:
            await self.session.flush()
        else:
            await self.session.commit()
        return objects

    async def update_by_id(self, record_id: int, **values: Any) -> Optional[ModelT]:
        stmt = (
            update(self.model)
            .where(self.model.id == record_id)  # type: ignore[attr-defined]
            .values(**values)
        )
        await self.session.execute(stmt)
        await self.session.commit()
        return await self.get_by_id(record_id)

    async def bulk_update(self, *filters: Any, **values: Any) -> int:
        stmt = update(self.model).where(*filters).values(**values)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount  # type: ignore[return-value]

    async def delete_by_id(self, record_id: int) -> bool:
        stmt = delete(self.model).where(
            self.model.id == record_id  # type: ignore[attr-defined]
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0  # type: ignore[operator]

    async def bulk_delete(self, *filters: Any) -> int:
        stmt = delete(self.model).where(*filters)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount  # type: ignore[return-value]

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _apply_filters(stmt: Select, filters: Optional[list]) -> Select:
        if filters:
            stmt = stmt.where(*filters)
        return stmt
