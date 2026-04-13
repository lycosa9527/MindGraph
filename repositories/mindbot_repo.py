"""Async repository for OrganizationMindbotConfig."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.mindbot_config import OrganizationMindbotConfig


class MindbotConfigRepository:
    """Load MindBot integration rows by public callback token or organization id."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_public_callback_token(self, token: str) -> Optional[OrganizationMindbotConfig]:
        result = await self._session.execute(
            select(OrganizationMindbotConfig).where(
                OrganizationMindbotConfig.public_callback_token == token,
            )
        )
        return result.scalar_one_or_none()

    async def get_enabled_by_public_callback_token(self, token: str) -> Optional[OrganizationMindbotConfig]:
        result = await self._session.execute(
            select(OrganizationMindbotConfig).where(
                OrganizationMindbotConfig.public_callback_token == token,
                OrganizationMindbotConfig.is_enabled.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_organization_id(self, organization_id: int) -> Optional[OrganizationMindbotConfig]:
        result = await self._session.execute(
            select(OrganizationMindbotConfig).where(
                OrganizationMindbotConfig.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_enabled_by_organization_id(self, organization_id: int) -> Optional[OrganizationMindbotConfig]:
        result = await self._session.execute(
            select(OrganizationMindbotConfig).where(
                OrganizationMindbotConfig.organization_id == organization_id,
                OrganizationMindbotConfig.is_enabled.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[OrganizationMindbotConfig]:
        result = await self._session.execute(
            select(OrganizationMindbotConfig).order_by(OrganizationMindbotConfig.organization_id)
        )
        return list(result.scalars().all())
