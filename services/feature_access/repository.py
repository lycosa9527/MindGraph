"""Load and persist feature access rules in the database."""

import logging
from typing import Dict

from sqlalchemy.orm import Session

from config.database import SessionLocal
from services.redis.cache import redis_feature_org_access_cache
from models.domain.auth import Organization, User
from models.domain.feature_access_control import (
    FeatureAccessOrgGrant,
    FeatureAccessRule,
    FeatureAccessUserGrant,
)
from models.domain.feature_org_access import FeatureOrgAccessEntry

logger = logging.getLogger(__name__)


def _validate_grant_fks(db: Session, data: Dict[str, FeatureOrgAccessEntry]) -> None:
    """Ensure organization and user ids exist before replacing grants."""
    org_ids = set()
    user_ids = set()
    for entry in data.values():
        org_ids.update(entry.organization_ids)
        user_ids.update(entry.user_ids)
    if org_ids:
        found = {row[0] for row in db.query(Organization.id).filter(Organization.id.in_(org_ids)).all()}
        missing = sorted(org_ids - found)
        if missing:
            raise ValueError(f"Unknown organization id(s): {missing}")
    if user_ids:
        found = {row[0] for row in db.query(User.id).filter(User.id.in_(user_ids)).all()}
        missing = sorted(user_ids - found)
        if missing:
            raise ValueError(f"Unknown user id(s): {missing}")


def load_feature_org_access_map() -> Dict[str, FeatureOrgAccessEntry]:
    """Read all rules and grants (Redis first, then Postgres)."""
    cached = redis_feature_org_access_cache.get_cached_map()
    if cached is not None:
        return cached
    db = SessionLocal()
    try:
        data = load_feature_org_access_session(db)
    finally:
        db.close()
    redis_feature_org_access_cache.set_cached_map(data)
    return data


def load_feature_org_access_session(db: Session) -> Dict[str, FeatureOrgAccessEntry]:
    """Read all rules and grants using an existing session."""
    rules = list(db.query(FeatureAccessRule).all())
    if not rules:
        return {}
    org_rows = db.query(FeatureAccessOrgGrant).all()
    user_rows = db.query(FeatureAccessUserGrant).all()
    org_by_key: Dict[str, list[int]] = {}
    for row in org_rows:
        org_by_key.setdefault(row.feature_key, []).append(row.organization_id)
    user_by_key: Dict[str, list[int]] = {}
    for row in user_rows:
        user_by_key.setdefault(row.feature_key, []).append(row.user_id)
    result: Dict[str, FeatureOrgAccessEntry] = {}
    for rule in rules:
        key = rule.feature_key
        result[key] = FeatureOrgAccessEntry(
            restrict=bool(rule.restrict),
            organization_ids=sorted(org_by_key.get(key, [])),
            user_ids=sorted(user_by_key.get(key, [])),
        )
    return result


def replace_feature_org_access(db: Session, data: Dict[str, FeatureOrgAccessEntry]) -> None:
    """Replace the entire access configuration (admin PUT)."""
    _validate_grant_fks(db, data)
    db.query(FeatureAccessOrgGrant).delete()
    db.query(FeatureAccessUserGrant).delete()
    db.query(FeatureAccessRule).delete()
    db.flush()
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
        db.commit()
    except Exception:
        db.rollback()
        raise
    redis_feature_org_access_cache.set_cached_map(data)
    logger.info("Replaced feature org access rules (%d features)", len(data))
