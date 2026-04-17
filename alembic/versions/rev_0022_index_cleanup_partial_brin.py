"""Schema cleanup: drop redundant indexes, add partial indexes, add BRIN for time-series.

Revision ID: 0022
Revises: 0021
Create Date: 2026-04-17

Phase 1 of the database & Redis performance plan.

Changes
-------
1. Drop single-column B-tree indexes that duplicate either a UNIQUE constraint
   (which already creates a unique index) or the leading column of an existing
   composite index. PostgreSQL can use the leading column of a composite for
   single-column predicates, so the standalone index is pure write amplification.

2. Convert low-cardinality boolean indexes (``is_deleted``, ``is_pinned``,
   ``is_archived``, ``is_read``) to **partial indexes** that only store rows
   matching the typical predicate. This dramatically shrinks index size and
   speeds up writes.

3. Add **BRIN** indexes on append-only time-series ``created_at`` columns
   (~1/100th the size of a B-tree, ideal for range scans).

4. Tighten the MindBot thread query composite to ``(organization_id,
   dingtalk_conversation_id, id DESC)`` so list endpoints use a single index.

All operations are wrapped in ``IF EXISTS`` / ``IF NOT EXISTS`` so the
migration is safe to apply against existing or fresh databases.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_REDUNDANT_INDEXES: dict[str, tuple[str, str]] = {
    "ix_users_phone": ("users", "phone"),
    "ix_users_email": ("users", "email"),
    "ix_organizations_code": ("organizations", "code"),
    "ix_api_keys_key": ("api_keys", "key"),
    "ix_diagrams_user_id": ("diagrams", "user_id"),
    "ix_mindbot_usage_events_organization_id": (
        "mindbot_usage_events",
        "organization_id",
    ),
    "ix_token_usage_user_id": ("token_usage", "user_id"),
    "ix_token_usage_organization_id": ("token_usage", "organization_id"),
    "ix_token_usage_api_key_id": ("token_usage", "api_key_id"),
}

_REDUNDANT_CREATED_AT_BTREES: dict[str, tuple[str, str]] = {
    "idx_token_usage_date": ("token_usage", "created_at"),
    "ix_token_usage_created_at": ("token_usage", "created_at"),
    "ix_mindbot_usage_events_created_at": (
        "mindbot_usage_events",
        "created_at",
    ),
    "ix_user_activity_log_created_at": ("user_activity_log", "created_at"),
}

_BOOLEAN_INDEXES_TO_DROP: dict[str, tuple[str, str]] = {
    "ix_diagrams_is_deleted": ("diagrams", "is_deleted"),
    "ix_diagrams_is_pinned": ("diagrams", "is_pinned"),
    "ix_chat_channels_is_archived": ("chat_channels", "is_archived"),
    "ix_direct_messages_is_read": ("direct_messages", "is_read"),
}

_PARTIAL_INDEXES: tuple[tuple[str, str, str, str], ...] = (
    (
        "ix_diagrams_active",
        "diagrams",
        "(user_id, updated_at DESC)",
        "NOT is_deleted",
    ),
    (
        "ix_diagrams_pinned",
        "diagrams",
        "(user_id)",
        "is_pinned",
    ),
    (
        "ix_dm_unread",
        "direct_messages",
        "(recipient_id, created_at DESC)",
        "NOT is_read AND NOT is_deleted",
    ),
    (
        "ix_chat_channels_active",
        "chat_channels",
        "(organization_id, name)",
        "NOT is_archived",
    ),
)

_BRIN_INDEXES: tuple[tuple[str, str, str], ...] = (
    ("ix_mindbot_usage_created_brin", "mindbot_usage_events", "created_at"),
    ("ix_token_usage_created_brin", "token_usage", "created_at"),
    ("ix_chat_messages_created_brin", "chat_messages", "created_at"),
    ("ix_direct_messages_created_brin", "direct_messages", "created_at"),
    ("ix_user_activity_created_brin", "user_activity_log", "created_at"),
)

_MINDBOT_THREAD_INDEX_NAME = "ix_mindbot_usage_org_thread_id"
_OLD_MINDBOT_THREAD_INDEX_NAME = "ix_mindbot_usage_dt_conv"


def _drop_index(name: str) -> None:
    """Idempotently drop an index by name."""
    op.execute(f'DROP INDEX IF EXISTS "{name}"')


def _create_index(sql: str) -> None:
    """Run a raw CREATE INDEX statement (already includes IF NOT EXISTS)."""
    op.execute(sql)


def upgrade() -> None:
    """Apply the schema cleanup."""
    for name in _REDUNDANT_INDEXES:
        _drop_index(name)
    for name in _REDUNDANT_CREATED_AT_BTREES:
        _drop_index(name)
    for name in _BOOLEAN_INDEXES_TO_DROP:
        _drop_index(name)
    _drop_index(_OLD_MINDBOT_THREAD_INDEX_NAME)

    for name, table, cols, where in _PARTIAL_INDEXES:
        _create_index(f'CREATE INDEX IF NOT EXISTS "{name}" ON "{table}" {cols} WHERE {where}')

    for name, table, column in _BRIN_INDEXES:
        _create_index(f'CREATE INDEX IF NOT EXISTS "{name}" ON "{table}" USING BRIN ("{column}")')

    _create_index(
        f'CREATE INDEX IF NOT EXISTS "{_MINDBOT_THREAD_INDEX_NAME}" '
        f'ON "mindbot_usage_events" '
        f'("organization_id", "dingtalk_conversation_id", "id" DESC)'
    )


def downgrade() -> None:
    """Revert the schema cleanup."""
    _drop_index(_MINDBOT_THREAD_INDEX_NAME)

    for name, _table, _column in _BRIN_INDEXES:
        _drop_index(name)

    for name, _table, _cols, _where in _PARTIAL_INDEXES:
        _drop_index(name)

    for name, (table, column) in _BOOLEAN_INDEXES_TO_DROP.items():
        _create_index(f'CREATE INDEX IF NOT EXISTS "{name}" ON "{table}" ("{column}")')

    for name, (table, column) in _REDUNDANT_CREATED_AT_BTREES.items():
        _create_index(f'CREATE INDEX IF NOT EXISTS "{name}" ON "{table}" ("{column}")')

    for name, (table, column) in _REDUNDANT_INDEXES.items():
        _create_index(f'CREATE INDEX IF NOT EXISTS "{name}" ON "{table}" ("{column}")')

    _create_index(
        f'CREATE INDEX IF NOT EXISTS "{_OLD_MINDBOT_THREAD_INDEX_NAME}" '
        f'ON "mindbot_usage_events" ("dingtalk_conversation_id")'
    )
