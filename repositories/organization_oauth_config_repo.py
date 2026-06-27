"""Repository for organization_oauth_configs."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.organization_oauth_config import OrganizationOauthConfig


class OrganizationOauthConfigRepository:
    """Persistence for per-org OAuth login settings."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_org(self, organization_id: int) -> Optional[OrganizationOauthConfig]:
        """Return OAuth config row for organization or None."""
        stmt = select(OrganizationOauthConfig).where(OrganizationOauthConfig.organization_id == int(organization_id))
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def get_or_create(self, organization_id: int) -> OrganizationOauthConfig:
        """Return existing config or insert defaults."""
        row = await self.get_by_org(organization_id)
        if row is not None:
            return row
        row = OrganizationOauthConfig(organization_id=int(organization_id))
        self._db.add(row)
        await self._db.flush()
        return row

    async def upsert(
        self,
        *,
        organization_id: int,
        wechat_login_enabled: Optional[bool] = None,
        dingtalk_login_enabled: Optional[bool] = None,
        dingtalk_login_app_key: Optional[str] = None,
        dingtalk_login_app_secret: Optional[str] = None,
        dingtalk_corp_id: Optional[str] = None,
        clear_dingtalk_secret: bool = False,
    ) -> OrganizationOauthConfig:
        """Patch org OAuth config fields."""
        row = await self.get_or_create(organization_id)
        if wechat_login_enabled is not None:
            row.wechat_login_enabled = bool(wechat_login_enabled)
        if dingtalk_login_enabled is not None:
            row.dingtalk_login_enabled = bool(dingtalk_login_enabled)
        if dingtalk_login_app_key is not None:
            key = (dingtalk_login_app_key or "").strip()
            row.dingtalk_login_app_key = key or None
        if clear_dingtalk_secret:
            row.dingtalk_login_app_secret = None
        elif dingtalk_login_app_secret is not None:
            secret = (dingtalk_login_app_secret or "").strip()
            if secret:
                row.dingtalk_login_app_secret = secret
        if dingtalk_corp_id is not None:
            corp = (dingtalk_corp_id or "").strip()
            row.dingtalk_corp_id = corp or None
        await self._db.flush()
        return row
