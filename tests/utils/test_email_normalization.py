"""Ensure API email normalization aligns with Redis key normalization."""

from __future__ import annotations

from email_validator import validate_email as ev_validate

from services.redis.redis_email_storage import normalize_verification_email


def test_redis_key_matches_validated_email_ascii() -> None:
    raw = "  User.Name+tag@Example.COM  "
    validated = ev_validate(raw.strip(), check_deliverability=False).normalized
    key = normalize_verification_email(validated)
    assert key == validated.strip().lower()


def test_redis_key_matches_validated_email_unicode_domain() -> None:
    raw = "user@münchen.de"
    validated = ev_validate(raw, check_deliverability=False).normalized
    key = normalize_verification_email(validated)
    assert key == validated.strip().lower()
