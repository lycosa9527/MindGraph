"""Generic async CRUD repository base.

Provides reusable async operations for any SQLAlchemy model so that
domain repositories only need to declare model-specific queries.

Write methods are flush-only by default so that multiple repository calls can
participate in a single transaction managed by the caller.  Pass
``commit=True`` only when the repository is the sole owner of the transaction
(e.g. standalone background tasks).
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

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Only concrete classes (those with model in their own __dict__) are
        # checked; generic or abstract intermediates are allowed to skip it.
        if "model" in cls.__dict__ and not isinstance(cls.__dict__["model"], type):
            raise TypeError(
                f"{cls.__name__}.model must be a SQLAlchemy model class, got {type(cls.__dict__['model'])!r}"
            )

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
        subq = select(self.model).where(*filters).exists()
        result = await self.session.execute(select(subq))
        return bool(result.scalar_one())

    # -- writes --------------------------------------------------------------

    async def create(self, obj: ModelT, *, commit: bool = False) -> ModelT:
        self.session.add(obj)
        if commit:
            await self.session.commit()
            await self.session.refresh(obj)
        else:
            await self.session.flush()
        return obj

    async def create_many(self, objects: Sequence[ModelT], *, commit: bool = False) -> Sequence[ModelT]:
        self.session.add_all(objects)
        if commit:
            await self.session.commit()
            for obj in objects:
                await self.session.refresh(obj)
        else:
            await self.session.flush()
        return objects

    async def update_by_id(self, record_id: int, *, commit: bool = False, **values: Any) -> Optional[ModelT]:
        stmt = (
            update(self.model)
            .where(self.model.id == record_id)
            .values(**values)
            .returning(
                self.model  # type: ignore[attr-defined]
            )
        )
        result = await self.session.execute(stmt)
        obj = result.scalars().one_or_none()
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()
        return obj

    async def bulk_update(self, *filters: Any, commit: bool = False, **values: Any) -> int:
        stmt = update(self.model).where(*filters).values(**values)
        result = await self.session.execute(stmt)
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()
        return result.rowcount  # type: ignore[return-value]

    async def delete_by_id(self, record_id: int, *, commit: bool = False) -> bool:
        stmt = delete(self.model).where(self.model.id == record_id)
        result = await self.session.execute(stmt)
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()
        return result.rowcount > 0  # type: ignore[operator]

    async def bulk_delete(self, *filters: Any, commit: bool = False) -> int:
        stmt = delete(self.model).where(*filters)
        result = await self.session.execute(stmt)
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()
        return result.rowcount  # type: ignore[return-value]

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _apply_filters(stmt: Select, filters: Optional[list]) -> Select:
        if filters:
            stmt = stmt.where(*filters)
        return stmt
