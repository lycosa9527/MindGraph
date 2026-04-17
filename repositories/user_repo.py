"""User & Organization async repository."""

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.domain.auth import APIKey, Organization, User

from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_phone(self, phone: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).options(selectinload(User.organization)).where(User.phone == phone)
        )
        return result.scalar_one_or_none()

    async def get_with_org(self, user_id: int) -> Optional[User]:
        result = await self.session.execute(
            select(User).options(selectinload(User.organization)).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_by_org(
        self,
        org_id: int,
        *,
        before_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[User]:
        """List members of an org ordered by ``id DESC`` (≈ newest first).

        Use ``before_id`` (the id of the last row on the previous page) for
        keyset pagination.  ``offset`` is retained for backward compatibility
        only; it is ignored when ``before_id`` is supplied.
        """
        conditions = [User.organization_id == org_id]
        if before_id is not None:
            conditions.append(User.id < before_id)
        stmt = select(User).where(*conditions).order_by(User.id.desc()).limit(limit)
        if before_id is None and offset:
            stmt = stmt.offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_by_org(self, org_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(User).where(User.organization_id == org_id)
        )
        return result.scalar_one()


class OrganizationRepository(BaseRepository[Organization]):
    model = Organization

    async def get_by_code(self, code: str) -> Optional[Organization]:
        result = await self.session.execute(select(Organization).where(Organization.code == code))
        return result.scalar_one_or_none()

    async def get_active(self) -> Sequence[Organization]:
        result = await self.session.execute(
            select(Organization).where(Organization.is_active.is_(True)).order_by(Organization.name)
        )
        return result.scalars().all()


class APIKeyRepository(BaseRepository[APIKey]):
    model = APIKey

    async def get_by_key(self, key: str) -> Optional[APIKey]:
        result = await self.session.execute(select(APIKey).where(APIKey.key == key, APIKey.is_active.is_(True)))
        return result.scalar_one_or_none()

    async def list_active(self) -> Sequence[APIKey]:
        result = await self.session.execute(
            select(APIKey).where(APIKey.is_active.is_(True)).order_by(APIKey.created_at.desc())
        )
        return result.scalars().all()


def get_user_repo(session: AsyncSession) -> UserRepository:
    return UserRepository(session)


def get_org_repo(session: AsyncSession) -> OrganizationRepository:
    return OrganizationRepository(session)


def get_api_key_repo(session: AsyncSession) -> APIKeyRepository:
    return APIKeyRepository(session)
