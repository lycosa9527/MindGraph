"""Tests for canonical role filter DB slug expansion."""

from utils.auth.role_constants import (
    LEGACY_ROLE_ADMIN,
    LEGACY_ROLE_MANAGER,
    LEGACY_ROLE_USER,
    ROLE_PERSONAL_PAID,
    ROLE_SCHOOL_ADMIN,
    ROLE_SUPERADMIN,
    ROLE_TEACHER,
    db_roles_for_canonical_filter,
)


def test_db_roles_for_canonical_filter_includes_legacy_slugs():
    """Canonical filters match both current and legacy DB role values."""
    assert db_roles_for_canonical_filter(ROLE_SUPERADMIN) == frozenset({ROLE_SUPERADMIN, LEGACY_ROLE_ADMIN})
    assert db_roles_for_canonical_filter(ROLE_SCHOOL_ADMIN) == frozenset({ROLE_SCHOOL_ADMIN, LEGACY_ROLE_MANAGER})
    assert db_roles_for_canonical_filter(ROLE_TEACHER) == frozenset({ROLE_TEACHER, LEGACY_ROLE_USER})


def test_db_roles_for_canonical_filter_without_legacy():
    """Roles without legacy aliases return only the canonical slug."""
    assert db_roles_for_canonical_filter(ROLE_PERSONAL_PAID) == frozenset({ROLE_PERSONAL_PAID})
