"""Load and persist feature access rules in the database."""

import logging
from typing import Dict

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import AsyncSessionLocal
from services.redis.cache import redis_feature_org_access_cache
from models.domain.auth import Organization, User
from models.domain.feature_access_control import (
    FeatureAccessOrgGrant,
    FeatureAccessRule,
    FeatureAccessUserGrant,
)
from models.domain.feature_org_access import FeatureOrgAccessEntry

logger = logging.getLogger(__name__)


async def _validate_grant_fks(db: AsyncSession, data: Dict[str, FeatureOrgAccessEntry]) -> None:
    """Ensure organization and user ids exist before replacing grants."""
    org_ids = set()
    user_ids = set()
    for entry in data.values():
        org_ids.update(entry.organization_ids)
        user_ids.update(entry.user_ids)
    if org_ids:
        result = await db.execute(select(Organization.id).where(Organization.id.in_(org_ids)))
        found = {row[0] for row in result.all()}
        missing = sorted(org_ids - found)
        if missing:
            raise ValueError(f"Unknown organization id(s): {missing}")
    if user_ids:
        result = await db.execute(select(User.id).where(User.id.in_(user_ids)))
        found = {row[0] for row in result.all()}
        missing = sorted(user_ids - found)
        if missing:
            raise ValueError(f"Unknown user id(s): {missing}")


async def load_feature_org_access_map() -> Dict[str, FeatureOrgAccessEntry]:
    """Read all rules and grants (Redis first, then Postgres)."""
    cached = redis_feature_org_access_cache.get_cached_map()
    if cached is not None:
        return cached
    async with AsyncSessionLocal() as db:
        data = await load_feature_org_access_session(db)
    redis_feature_org_access_cache.set_cached_map(data)
    return data


async def load_feature_org_access_session(db: AsyncSession) -> Dict[str, FeatureOrgAccessEntry]:
    """Read all rules and grants using an existing session."""
    result = await db.execute(select(FeatureAccessRule))
    rules = list(result.scalars().all())
    if not rules:
        return {}
    org_result = await db.execute(select(FeatureAccessOrgGrant))
    org_rows = org_result.scalars().all()
    user_result = await db.execute(select(FeatureAccessUserGrant))
    user_rows = user_result.scalars().all()
    org_by_key: Dict[str, list[int]] = {}
    for row in org_rows:
        org_by_key.setdefault(row.feature_key, []).append(row.organization_id)
    user_by_key: Dict[str, list[int]] = {}
    for row in user_rows:
        user_by_key.setdefault(row.feature_key, []).append(row.user_id)
    result_map: Dict[str, FeatureOrgAccessEntry] = {}
    for rule in rules:
        key = rule.feature_key
        result_map[key] = FeatureOrgAccessEntry(
            restrict=bool(rule.restrict),
            organization_ids=sorted(org_by_key.get(key, [])),
            user_ids=sorted(user_by_key.get(key, [])),
        )
    return result_map


async def replace_feature_org_access(db: AsyncSession, data: Dict[str, FeatureOrgAccessEntry]) -> None:
    """Replace the entire access configuration (admin PUT)."""
    await _validate_grant_fks(db, data)
    await db.execute(delete(FeatureAccessOrgGrant))
    await db.execute(delete(FeatureAccessUserGrant))
    await db.execute(delete(FeatureAccessRule))
    await db.flush()
    for feature_key, entry in data.items():
        db.add(
            FeatureAccessRule(
                feature_key=feature_key,
                restrict=entry.restrict,
            )
        )
        for oid in sorted(set(entry.organization_ids)):
            db.add(
                FeatureAccessOrgGrant(
                    feature_key=feature_key,
                    organization_id=oid,
                )
            )
        for uid in sorted(set(entry.user_ids)):
            db.add(
                FeatureAccessUserGrant(
                    feature_key=feature_key,
                    user_id=uid,
                )
            )
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    redis_feature_org_access_cache.set_cached_map(data)
    logger.info("Replaced feature org access rules (%d features)", len(data))
