"""Regression: community engagement RLS must allow panel/system writes.

Authenticated likers/commenters bump another author's counters via system
sessions; moderation and user-delete cascades remove others' likes/comments.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (_REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_community_panel_system_migration_widens_writes() -> None:
    """rev_0096 must add panel/system write modes on community engagement tables."""
    text = _read("alembic/versions/rev_0096_rls_community_panel_system.py")
    assert 'down_revision: Union[str, None] = "0095"' in text
    assert "rls_is_panel_mode()" in text
    assert "rls_is_system_mode()" in text
    assert "community_posts" in text
    assert "community_post_likes" in text
    assert "community_post_comments" in text


def test_policy_builder_community_writes_include_system() -> None:
    """Greenfield policy builder must keep system mode on community writes."""
    text = _read("db_rls/policy_builder.py")
    assert "OR rls_is_system_mode()" in text
    assert '("community_post_likes", COMMUNITY_READ, COMMUNITY_WRITE)' in text


def test_community_like_uses_system_counter_helper() -> None:
    """Like/comment routes must bump counters through system_bootstrap helpers."""
    router = _read("routers/features/community/__init__.py")
    counters = _read("routers/features/community/counters.py")
    assert "adjust_post_likes_count" in router
    assert "adjust_post_comments_count" in router
    assert "system_bootstrap" in router
    assert "panel_superadmin" not in router
    assert "system_bootstrap" in counters


def test_proxy_auto_approve_does_not_credit_thinking_coins() -> None:
    """Admin proxy auto-approve path must not credit thinking coins itself."""
    text = _read("routers/features/showcase/admin.py")
    assert "try_publish_case_earn" not in text
    assert "credited_coins" not in text
