"""
Async repository for market (市场) tables.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import UTC, datetime
from typing import Optional, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.domain.markets import (
    MarketEntitlement,
    MarketListing,
    MarketOrder,
    MarketPayment,
    MarketSubscription,
)
from models.domain.auth import User

from .base import BaseRepository


class MarketListingRepository(BaseRepository[MarketListing]):
    model = MarketListing

    async def list_active(
        self,
        *,
        listing_kind: Optional[str] = None,
        scene: Optional[str] = None,
        subject: Optional[str] = None,
        product_type: Optional[str] = None,
        after_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[MarketListing]:
        """Active market listings ordered by ``id ASC``.

        Prefer ``after_id`` (id of the last row returned) over ``offset`` for
        keyset pagination; ``offset`` remains for backwards compatibility.
        """
        stmt = select(MarketListing).where(MarketListing.is_active.is_(True))
        if listing_kind:
            stmt = stmt.where(MarketListing.listing_kind == listing_kind)
        if scene and scene != "全部":
            stmt = stmt.where(MarketListing.scene == scene)
        if subject and subject != "全部":
            stmt = stmt.where(MarketListing.subject == subject)
        if product_type and product_type != "全部":
            stmt = stmt.where(MarketListing.product_type == product_type)
        if after_id is not None:
            stmt = stmt.where(MarketListing.id > after_id)
        stmt = stmt.order_by(MarketListing.id.asc()).limit(limit)
        if after_id is None and offset:
            stmt = stmt.offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_slug(self, slug: str) -> Optional[MarketListing]:
        result = await self.session.execute(
            select(MarketListing).where(MarketListing.slug == slug, MarketListing.is_active.is_(True))
        )
        return result.scalar_one_or_none()


class MarketOrderRepository(BaseRepository[MarketOrder]):
    model = MarketOrder

    async def get_by_out_trade_no(self, out_trade_no: str) -> Optional[MarketOrder]:
        result = await self.session.execute(select(MarketOrder).where(MarketOrder.out_trade_no == out_trade_no))
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: int,
        *,
        before_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[MarketOrder]:
        """User's orders ordered by ``id DESC`` (≈ newest first)."""
        conditions = [MarketOrder.user_id == user_id]
        if before_id is not None:
            conditions.append(MarketOrder.id < before_id)
        stmt = (
            select(MarketOrder)
            .options(selectinload(MarketOrder.listing))
            .where(*conditions)
            .order_by(MarketOrder.id.desc())
            .limit(limit)
        )
        if before_id is None and offset:
            stmt = stmt.offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def admin_list(
        self,
        *,
        status: Optional[str] = None,
        before_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[MarketOrder]:
        """Admin order list ordered by ``id DESC``.

        Prefer ``before_id`` keyset cursor over ``offset`` to keep deep
        admin pages cheap on the orders table.
        """
        stmt = select(MarketOrder).options(
            selectinload(MarketOrder.listing),
            selectinload(MarketOrder.user),
            selectinload(MarketOrder.payment),
        )
        if status:
            stmt = stmt.where(MarketOrder.status == status)
        if before_id is not None:
            stmt = stmt.where(MarketOrder.id < before_id)
        stmt = stmt.order_by(MarketOrder.id.desc()).limit(limit)
        if before_id is None and offset:
            stmt = stmt.offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_admin(self, *, status: Optional[str] = None) -> int:
        stmt = select(func.count()).select_from(MarketOrder)
        if status:
            stmt = stmt.where(MarketOrder.status == status)
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)


class MarketPaymentRepository(BaseRepository[MarketPayment]):
    model = MarketPayment

    async def get_by_notify_id(self, notify_id: str) -> Optional[MarketPayment]:
        if not notify_id:
            return None
        result = await self.session.execute(select(MarketPayment).where(MarketPayment.notify_id == notify_id))
        return result.scalar_one_or_none()


class MarketEntitlementRepository(BaseRepository[MarketEntitlement]):
    model = MarketEntitlement

    @staticmethod
    def is_row_active(row: Optional[MarketEntitlement]) -> bool:
        if row is None:
            return False
        if row.expires_at is None:
            return True
        now = datetime.now(UTC).replace(tzinfo=None)
        return row.expires_at > now

    async def get_for_user_listing(self, user_id: int, listing_id: int) -> Optional[MarketEntitlement]:
        result = await self.session.execute(
            select(MarketEntitlement).where(
                MarketEntitlement.user_id == user_id,
                MarketEntitlement.listing_id == listing_id,
            )
        )
        return result.scalar_one_or_none()

    async def has_entitlement(self, user_id: int, listing_id: int) -> bool:
        row = await self.get_for_user_listing(user_id, listing_id)
        return self.is_row_active(row)

    async def list_active_for_user(self, user_id: int) -> Sequence[MarketEntitlement]:
        now = datetime.now(UTC).replace(tzinfo=None)
        result = await self.session.execute(
            select(MarketEntitlement)
            .options(selectinload(MarketEntitlement.listing))
            .where(
                MarketEntitlement.user_id == user_id,
                or_(MarketEntitlement.expires_at.is_(None), MarketEntitlement.expires_at > now),
            )
            .order_by(MarketEntitlement.created_at.desc())
        )
        return result.scalars().all()


class MarketSubscriptionRepository(BaseRepository[MarketSubscription]):
    model = MarketSubscription

    async def get_open_for_user_listing(self, user_id: int, listing_id: int) -> Optional[MarketSubscription]:
        result = await self.session.execute(
            select(MarketSubscription)
            .options(selectinload(MarketSubscription.listing))
            .where(
                MarketSubscription.user_id == user_id,
                MarketSubscription.listing_id == listing_id,
                MarketSubscription.status.in_(("pending", "active", "past_due")),
            )
            .order_by(MarketSubscription.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_external_agreement_no(self, external_agreement_no: str) -> Optional[MarketSubscription]:
        result = await self.session.execute(
            select(MarketSubscription)
            .options(selectinload(MarketSubscription.listing))
            .where(MarketSubscription.external_agreement_no == external_agreement_no)
        )
        return result.scalar_one_or_none()

    async def get_by_agreement_id(self, agreement_no: str) -> Optional[MarketSubscription]:
        result = await self.session.execute(
            select(MarketSubscription)
            .options(selectinload(MarketSubscription.listing))
            .where(MarketSubscription.alipay_agreement_id == agreement_no)
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: int) -> Sequence[MarketSubscription]:
        result = await self.session.execute(
            select(MarketSubscription)
            .options(selectinload(MarketSubscription.listing))
            .where(MarketSubscription.user_id == user_id)
            .order_by(MarketSubscription.created_at.desc())
        )
        return result.scalars().all()

    async def admin_list(
        self,
        *,
        before_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[MarketSubscription]:
        """Admin subscription list ordered by ``id DESC``."""
        stmt = (
            select(MarketSubscription)
            .options(selectinload(MarketSubscription.listing), selectinload(MarketSubscription.user))
            .order_by(MarketSubscription.id.desc())
            .limit(limit)
        )
        if before_id is not None:
            stmt = stmt.where(MarketSubscription.id < before_id)
        elif offset:
            stmt = stmt.offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class MarketUserLookup:
    """Minimal user fields for admin responses."""

    @staticmethod
    async def get_email_or_phone(session: AsyncSession, user_id: int) -> Optional[str]:
        result = await session.execute(select(User.email, User.phone).where(User.id == user_id))
        row = result.one_or_none()
        if row is None:
            return None
        email, phone = row[0], row[1]
        if email:
            return str(email)
        if phone:
            return str(phone)
        return None
