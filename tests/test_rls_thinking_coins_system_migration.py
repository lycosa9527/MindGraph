"""Regression: case-approve credits author wallets without panel wallet writes.

rev_0066 scoped thinking-coin tables to owner only. Admin approve switches to
the author's RLS for the credit; rev_0095 adds system mode for privileged
cleanup (user delete) only — not blanket panel wallet access.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (_REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_thinking_coin_system_rls_migration_is_owner_or_system() -> None:
    """rev_0095 must allow system mode on coin tables without panel mode."""
    text = _read("alembic/versions/rev_0095_rls_thinking_coins_system.py")
    assert 'down_revision: Union[str, None] = "0094"' in text
    assert "rls_is_system_mode()" in text
    assert "rls_is_panel_mode()" not in text
    assert "thinking_coin_wallets" in text
    assert "thinking_coin_ledger" in text


def test_showcase_review_credits_under_author_rls() -> None:
    """Approve path must credit under the author's RLS via nested savepoint."""
    common = _read("routers/features/showcase/common.py")
    earn = _read("services/auth/thinking_coin/case_earn.py")
    assert "try_publish_case_earn_as_author" in common
    assert "for_celery_user" in earn
    assert "begin_nested()" in earn
    assert "*DATABASE_ERRORS" in common


def test_user_fk_cleanup_deletes_coins_under_system_rls() -> None:
    """User delete must wipe coin rows under system_bootstrap RLS."""
    text = _read("services/auth/user_fk_cleanup.py")
    assert "_delete_thinking_coins_for_user" in text
    assert "system_bootstrap" in text
