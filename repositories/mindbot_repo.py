"""Async repository for OrganizationMindbotConfig."""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.mindbot_config import OrganizationMindbotConfig

_LIST_ALL_MAX = 200
_BOT_CAP_PER_ORG = 5


class MindbotConfigRepository:
    """Load and count MindBot integration rows by various lookup keys."""

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

    async def get_by_id(self, config_id: int) -> Optional[OrganizationMindbotConfig]:
        result = await self._session.execute(
            select(OrganizationMindbotConfig).where(
                OrganizationMindbotConfig.id == config_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_organization_id(self, organization_id: int) -> list[OrganizationMindbotConfig]:
        """Return all configs for one school ordered by id ascending."""
        result = await self._session.execute(
            select(OrganizationMindbotConfig)
            .where(OrganizationMindbotConfig.organization_id == organization_id)
            .order_by(OrganizationMindbotConfig.id)
        )
        return list(result.scalars().all())

    async def count_by_organization_id(self, organization_id: int) -> int:
        """Return the number of configs for one school (used for the 5-bot cap check)."""
        result = await self._session.execute(
            select(func.count()).where(
                OrganizationMindbotConfig.organization_id == organization_id,
            )
        )
        return result.scalar_one()

    async def list_all(
        self,
        *,
        limit: int = 200,
        after_id: Optional[int] = None,
    ) -> list[OrganizationMindbotConfig]:
        """Return configs ordered by (organization_id ASC, id ASC) with cursor pagination.

        ``after_id`` is the exclusive lower bound on ``id`` (config primary key)
        so the caller can page forward by passing the last ``id`` seen.
        ``limit`` is capped at ``_LIST_ALL_MAX`` to prevent runaway queries.
        """
        effective_limit = min(max(1, limit), _LIST_ALL_MAX)
        query = select(OrganizationMindbotConfig)
        if after_id is not None:
            query = query.where(OrganizationMindbotConfig.id > after_id)
        query = query.order_by(
            OrganizationMindbotConfig.organization_id,
            OrganizationMindbotConfig.id,
        ).limit(effective_limit)
        result = await self._session.execute(query)
        return list(result.scalars().all())
