"""Check B2C market access for product gating."""

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.markets_repo import MarketEntitlementRepository, MarketListingRepository


async def user_has_listing_access(session: AsyncSession, user_id: int, listing_slug: str) -> bool:
    """User has listing access."""
    listing_repo = MarketListingRepository(session)
    listing = await listing_repo.get_by_slug(listing_slug)
    if listing is None:
        return False
    ent_repo = MarketEntitlementRepository(session)
    return await ent_repo.has_entitlement(user_id, listing.id)
