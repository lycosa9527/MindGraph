"""
PostgreSQL GIN indexes for workshop chat message full-text search.
"""

import logging
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)


def ensure_workshop_message_fts_indexes(conn: Any) -> None:
    """Create GIN indexes on message ``content`` for full-text search (idempotent)."""
    statements = (
        (
            "CREATE INDEX IF NOT EXISTS ix_chat_messages_fts_content "
            "ON chat_messages USING gin (to_tsvector('simple', content))"
        ),
        (
            "CREATE INDEX IF NOT EXISTS ix_direct_messages_fts_content "
            "ON direct_messages USING gin (to_tsvector('simple', content))"
        ),
    )
    for stmt in statements:
        try:
            conn.execute(text(stmt))
            conn.commit()
            logger.info("[DBMigration] Ensured FTS index: %s...", stmt[:50])
        except Exception as exc:
            logger.warning(
                "[DBMigration] FTS index creation skipped: %s",
                exc,
            )
            try:
                conn.rollback()
            except Exception:
                pass
