"""Tests for pg_restore preparation helpers."""

from __future__ import annotations

from services.utils.pg_restore_prep import _pg_restore_line_should_skip_for_migrate_role


def test_pg_restore_skip_extension_entries() -> None:
    assert _pg_restore_line_should_skip_for_migrate_role("316; 1259 12345 EXTENSION - pg_stat_statements")
    assert _pg_restore_line_should_skip_for_migrate_role("317; 0 0 COMMENT - EXTENSION pg_stat_statements")
    assert not _pg_restore_line_should_skip_for_migrate_role("; Archive created at Mon Jul 27 2026")
    assert not _pg_restore_line_should_skip_for_migrate_role("4123; 1259 999 TABLE public users postgres")


def test_pg_restore_skip_default_acl_entries() -> None:
    assert _pg_restore_line_should_skip_for_migrate_role(
        "2552; 826 470637 DEFAULT ACL public DEFAULT PRIVILEGES FOR SEQUENCES postgres"
    )
    assert _pg_restore_line_should_skip_for_migrate_role(
        "2553; 826 470760 DEFAULT ACL public DEFAULT PRIVILEGES FOR TABLES mindgraph_migrate"
    )
    assert not _pg_restore_line_should_skip_for_migrate_role(
        "3774; 2604 450012 DEFAULT public api_keys id mindgraph_migrate"
    )


def test_pg_restore_skip_ignores_comments() -> None:
    assert not _pg_restore_line_should_skip_for_migrate_role("; 316; 1259 EXTENSION - pg_stat_statements")
