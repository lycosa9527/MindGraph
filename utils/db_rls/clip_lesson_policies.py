"""Row-level security for clip-teaching lessons, chapters, and comments.

Same-organization members can read. The lesson owner writes the lesson,
chapters, and trim. Any member of that organization can insert a comment.
The author or the lesson owner can update or delete a comment.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

LESSON_READ = "rls_is_system_mode() OR rls_org_visible(organization_id)"
LESSON_WRITE = "rls_is_system_mode() OR (owner_id = rls_current_user_id() AND rls_org_visible(organization_id))"
CHAPTER_READ = (
    "rls_is_system_mode() OR EXISTS ("
    "SELECT 1 FROM clip_lessons l "
    "WHERE l.id = lesson_id AND rls_org_visible(l.organization_id)"
    ")"
)
CHAPTER_WRITE = (
    "rls_is_system_mode() OR EXISTS ("
    "SELECT 1 FROM clip_lessons l "
    "WHERE l.id = lesson_id AND l.owner_id = rls_current_user_id() "
    "AND rls_org_visible(l.organization_id)"
    ")"
)
COMMENT_READ = CHAPTER_READ
COMMENT_INSERT = (
    "rls_is_system_mode() OR ("
    "user_id = rls_current_user_id() AND EXISTS ("
    "SELECT 1 FROM clip_lessons l "
    "WHERE l.id = lesson_id AND rls_org_visible(l.organization_id)"
    "))"
)
COMMENT_UPDATE = (
    "rls_is_system_mode() OR ("
    "EXISTS ("
    "SELECT 1 FROM clip_lessons l "
    "WHERE l.id = lesson_id AND rls_org_visible(l.organization_id)"
    ") AND ("
    "user_id = rls_current_user_id() OR EXISTS ("
    "SELECT 1 FROM clip_lessons owner_lesson "
    "WHERE owner_lesson.id = lesson_id "
    "AND owner_lesson.owner_id = rls_current_user_id()"
    ")))"
)

_TABLES = ("clip_lessons", "clip_lesson_chapters", "clip_lesson_comments")


def _enable(table: str) -> bool:
    if not sa.inspect(op.get_bind()).has_table(table):
        return False
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
    return True


def _policy(table: str, suffix: str, command: str, expression: str, *, check: bool) -> None:
    if check and command == "INSERT":
        op.execute(sa.text(f'CREATE POLICY "{table}_{suffix}" ON "{table}" FOR INSERT WITH CHECK ({expression})'))
        return
    if check and command == "UPDATE":
        op.execute(
            sa.text(
                f'CREATE POLICY "{table}_{suffix}" ON "{table}" '
                f"FOR UPDATE USING ({expression}) WITH CHECK ({expression})"
            )
        )
        return
    op.execute(sa.text(f'CREATE POLICY "{table}_{suffix}" ON "{table}" FOR {command} USING ({expression})'))


def install_clip_lesson_policies() -> None:
    """Create the current policies. Skips a table that is not created yet."""
    if _enable("clip_lessons"):
        _policy("clip_lessons", "select", "SELECT", LESSON_READ, check=False)
        _policy("clip_lessons", "write", "INSERT", LESSON_WRITE, check=True)
        _policy("clip_lessons", "update", "UPDATE", LESSON_WRITE, check=True)
        _policy("clip_lessons", "delete", "DELETE", LESSON_WRITE, check=False)
    if _enable("clip_lesson_chapters"):
        _policy("clip_lesson_chapters", "select", "SELECT", CHAPTER_READ, check=False)
        _policy("clip_lesson_chapters", "write", "INSERT", CHAPTER_WRITE, check=True)
        _policy("clip_lesson_chapters", "update", "UPDATE", CHAPTER_WRITE, check=True)
        _policy("clip_lesson_chapters", "delete", "DELETE", CHAPTER_WRITE, check=False)
    if _enable("clip_lesson_comments"):
        _policy("clip_lesson_comments", "select", "SELECT", COMMENT_READ, check=False)
        _policy("clip_lesson_comments", "write", "INSERT", COMMENT_INSERT, check=True)
        _policy("clip_lesson_comments", "update", "UPDATE", COMMENT_UPDATE, check=True)
        _policy("clip_lesson_comments", "delete", "DELETE", COMMENT_UPDATE, check=False)


def clip_lesson_table_names() -> tuple[str, ...]:
    """Tables this module installs."""
    return _TABLES
