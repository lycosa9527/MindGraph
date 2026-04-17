"""Async repository for OrganizationMindbotConfig."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.mindbot_config import OrganizationMindbotConfig

_LIST_ALL_MAX = 200


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

    async def list_all(
        self,
        *,
        limit: int = 50,
        after_org_id: Optional[int] = None,
    ) -> list[OrganizationMindbotConfig]:
        """Return configs ordered by organization_id ascending with cursor pagination.

        ``after_org_id`` is the exclusive lower bound on ``organization_id`` so the
        caller can page forward by passing the last ``organization_id`` seen.
        ``limit`` is capped at ``_LIST_ALL_MAX`` to prevent runaway queries.
        """
        effective_limit = min(max(1, limit), _LIST_ALL_MAX)
        query = select(OrganizationMindbotConfig)
        if after_org_id is not None:
            query = query.where(OrganizationMindbotConfig.organization_id > after_org_id)
        query = query.order_by(OrganizationMindbotConfig.organization_id).limit(effective_limit)
        result = await self._session.execute(query)
        return list(result.scalars().all())
