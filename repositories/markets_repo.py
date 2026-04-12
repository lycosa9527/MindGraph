"""Async repository for market (市场) tables."""

from typing import Optional, Sequence

from sqlalchemy import func, select
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
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[MarketListing]:
        stmt = select(MarketListing).where(MarketListing.is_active.is_(True))
        if listing_kind:
            stmt = stmt.where(MarketListing.listing_kind == listing_kind)
        if scene and scene != "全部":
            stmt = stmt.where(MarketListing.scene == scene)
        if subject and subject != "全部":
            stmt = stmt.where(MarketListing.subject == subject)
        if product_type and product_type != "全部":
            stmt = stmt.where(MarketListing.product_type == product_type)
        stmt = stmt.order_by(MarketListing.id.asc()).offset(offset).limit(limit)
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

    async def list_for_user(self, user_id: int, *, offset: int = 0, limit: int = 50) -> Sequence[MarketOrder]:
        result = await self.session.execute(
            select(MarketOrder)
            .options(selectinload(MarketOrder.listing))
            .where(MarketOrder.user_id == user_id)
            .order_by(MarketOrder.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def admin_list(
        self,
        *,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[MarketOrder]:
        stmt = select(MarketOrder).options(
            selectinload(MarketOrder.listing),
            selectinload(MarketOrder.user),
            selectinload(MarketOrder.payment),
        )
        if status:
            stmt = stmt.where(MarketOrder.status == status)
        stmt = stmt.order_by(MarketOrder.created_at.desc()).offset(offset).limit(limit)
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

    async def has_entitlement(self, user_id: int, listing_id: int) -> bool:
        result = await self.session.execute(
            select(MarketEntitlement.id).where(
                MarketEntitlement.user_id == user_id,
                MarketEntitlement.listing_id == listing_id,
            )
        )
        return result.scalar_one_or_none() is not None


class MarketSubscriptionRepository(BaseRepository[MarketSubscription]):
    model = MarketSubscription

    async def list_for_user(self, user_id: int) -> Sequence[MarketSubscription]:
        result = await self.session.execute(
            select(MarketSubscription)
            .options(selectinload(MarketSubscription.listing))
            .where(MarketSubscription.user_id == user_id)
            .order_by(MarketSubscription.created_at.desc())
        )
        return result.scalars().all()

    async def admin_list(self, *, offset: int = 0, limit: int = 50) -> Sequence[MarketSubscription]:
        result = await self.session.execute(
            select(MarketSubscription)
            .options(selectinload(MarketSubscription.listing), selectinload(MarketSubscription.user))
            .order_by(MarketSubscription.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
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
