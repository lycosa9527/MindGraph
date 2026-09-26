"""ORM tables must be named by an RLS migration, and the late policies stay tight."""

from __future__ import annotations

import re
from pathlib import Path

from models.domain.registry import Base
from utils.db_rls.gap_policies import (
    ERROR_EXPR,
    OAUTH_CONFIG_READ,
    OAUTH_CONFIG_WRITE,
    OAUTH_LINK_EXPR,
    PREVIEW_EXPR,
    STAFF_LINK_READ,
    STAFF_LINK_WRITE,
    THINKING_CATALOG_READ,
    THINKING_CATALOG_WRITE,
)

_ROOT = Path(__file__).resolve().parents[1]
_RLS_ROOTS = (_ROOT / "alembic" / "versions", _ROOT / "utils" / "db_rls")


def _orm_tables() -> set[str]:
    return set(Base.metadata.tables)


def _tables_named_in_rls_sources() -> set[str]:
    named: set[str] = set()
    orm = _orm_tables()
    for folder in _RLS_ROOTS:
        for path in folder.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "ROW LEVEL SECURITY" not in text:
                continue
            named.update(name for name in re.findall(r'["\']([a-z][a-z0-9_]{2,})["\']', text) if name in orm)
    return named


def test_every_orm_table_is_covered_by_rls_sql() -> None:
    """A new model table fails this until a policy migration names it."""
    missing = sorted(_orm_tables() - _tables_named_in_rls_sources())
    assert not missing, "ORM tables with no RLS policy source:\n" + "\n".join(missing)


def test_oauth_secret_writes_are_global_panel_or_system() -> None:
    """School members may read their own login config; they cannot change the secret."""
    assert "rls_org_visible(organization_id)" in OAUTH_CONFIG_READ
    assert "rls_panel_global_read()" in OAUTH_CONFIG_WRITE
    assert "rls_org_visible" not in OAUTH_CONFIG_WRITE


def test_error_logs_are_not_school_visible() -> None:
    """Stack traces stay on system collectors and global panel readers."""
    assert "rls_is_system_mode()" in ERROR_EXPR
    assert "rls_panel_global_read()" in ERROR_EXPR
    assert "rls_org_visible" not in ERROR_EXPR


def test_preview_specs_follow_the_owner() -> None:
    """Preview JSON is the owner's row, not every classmate's."""
    assert "user_id = rls_current_user_id()" in PREVIEW_EXPR
    assert "rls_same_org_users" not in PREVIEW_EXPR


def test_staff_link_writes_are_tighter_than_reads() -> None:
    """Conflict checks can see the org; a member cannot rewrite someone else's link."""
    assert "rls_org_visible(organization_id)" in STAFF_LINK_READ
    assert "user_id = rls_current_user_id()" in STAFF_LINK_WRITE
    assert "rls_org_visible(organization_id) OR user_id" not in STAFF_LINK_WRITE


def test_oauth_links_are_owner_system_or_panel() -> None:
    """Unscoped WeChat login uses system mode; a user cannot list another school's links."""
    assert "rls_is_system_mode()" in OAUTH_LINK_EXPR
    assert "user_id = rls_current_user_id()" in OAUTH_LINK_EXPR
    assert "rls_is_panel_mode()" in OAUTH_LINK_EXPR


def test_thinking_catalog_reads_are_broader_than_writes() -> None:
    """Signed-in users load earn tasks; only global panel or system edits them."""
    assert "rls_community_read_allowed()" in THINKING_CATALOG_READ
    assert "rls_panel_global_read()" in THINKING_CATALOG_WRITE
    assert "rls_community_read_allowed()" not in THINKING_CATALOG_WRITE
