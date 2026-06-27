"""Repository for oauth_user_links."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.oauth_user_link import (
    OAUTH_PROVIDERS,
    OauthUserLink,
)
from services.utils.typing_helpers import result_rowcount


class OauthUserLinkRepository:
    """Persistence for OAuth identity to user links."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    @staticmethod
    def _normalize_provider(provider: str) -> str:
        p = (provider or "").strip().lower()
        if p not in OAUTH_PROVIDERS:
            raise ValueError("invalid_provider")
        return p

    async def get_by_external(
        self,
        organization_id: int,
        provider: str,
        external_id: str,
    ) -> Optional[OauthUserLink]:
        """Lookup link by org + provider + external id."""
        ext = (external_id or "").strip()[:128]
        if not ext:
            return None
        prov = self._normalize_provider(provider)
        stmt = select(OauthUserLink).where(
            OauthUserLink.organization_id == int(organization_id),
            OauthUserLink.provider == prov,
            OauthUserLink.external_id == ext,
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def get_for_user(
        self,
        organization_id: int,
        user_id: int,
        provider: str,
    ) -> Optional[OauthUserLink]:
        """Return user's link for provider in org."""
        prov = self._normalize_provider(provider)
        stmt = select(OauthUserLink).where(
            OauthUserLink.organization_id == int(organization_id),
            OauthUserLink.user_id == int(user_id),
            OauthUserLink.provider == prov,
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def list_for_user(
        self,
        organization_id: int,
        user_id: int,
    ) -> list[OauthUserLink]:
        """All OAuth links for user in org."""
        stmt = select(OauthUserLink).where(
            OauthUserLink.organization_id == int(organization_id),
            OauthUserLink.user_id == int(user_id),
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def upsert_link(
        self,
        *,
        organization_id: int,
        user_id: int,
        provider: str,
        external_id: str,
        openid: Optional[str] = None,
        nickname: Optional[str] = None,
        linked_via: str = "self",
    ) -> OauthUserLink:
        """Create or update OAuth link for user."""
        prov = self._normalize_provider(provider)
        ext = (external_id or "").strip()[:128]
        if not ext:
            raise ValueError("external_id_required")

        existing_ext = await self.get_by_external(organization_id, prov, ext)
        if existing_ext is not None and int(existing_ext.user_id) != int(user_id):
            raise ValueError("external_id_taken")

        row = await self.get_for_user(organization_id, user_id, prov)
        if row is None:
            row = OauthUserLink(
                organization_id=int(organization_id),
                user_id=int(user_id),
                provider=prov,
                external_id=ext,
            )
            self._db.add(row)
        else:
            row.external_id = ext

        if openid is not None:
            row.openid = (openid or "").strip()[:128] or None
        if nickname is not None:
            nick = (nickname or "").strip()[:128]
            row.nickname = nick or None
        row.linked_via = (linked_via or "self")[:32]
        row.linked_at = datetime.now(UTC)
        await self._db.flush()
        return row

    async def delete_for_user(
        self,
        organization_id: int,
        user_id: int,
        provider: str,
    ) -> bool:
        """Remove user's OAuth link for provider."""
        prov = self._normalize_provider(provider)
        stmt = delete(OauthUserLink).where(
            OauthUserLink.organization_id == int(organization_id),
            OauthUserLink.user_id == int(user_id),
            OauthUserLink.provider == prov,
        )
        result = await self._db.execute(stmt)
        await self._db.flush()
        return result_rowcount(result) > 0

    async def resolve_user_id(
        self,
        organization_id: int,
        provider: str,
        external_id: str,
    ) -> Optional[int]:
        """Return MindGraph user id for external identity or None."""
        row = await self.get_by_external(organization_id, provider, external_id)
        if row is None:
            return None
        return int(row.user_id)
