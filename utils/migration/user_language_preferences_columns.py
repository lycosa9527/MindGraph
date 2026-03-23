"""
Ensure ``users.ui_language`` and ``users.prompt_language`` exist.

PostgreSQL: added by ORM ``run_migrations``. SQLite needs explicit ALTER.
"""

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, ProgrammingError

logger = logging.getLogger(__name__)

_TABLE = "users"
_COLUMNS = (
    ("ui_language", "VARCHAR(32)", "VARCHAR(32) NULL"),
    ("prompt_language", "VARCHAR(32)", "VARCHAR(32) NULL"),
)


def ensure_user_language_preferences_columns(engine: Engine) -> None:
    """Add UI / prompt language columns on ``users`` if missing (SQLite / PG fallback)."""
    try:
        inspector = inspect(engine)
        if _TABLE not in inspector.get_table_names():
            return

        existing = {col["name"] for col in inspector.get_columns(_TABLE)}
        dialect = engine.dialect.name
        if dialect not in ("sqlite", "postgresql"):
            return

        quoted_table = f'"{_TABLE}"' if dialect == "postgresql" else _TABLE

        with engine.begin() as conn:
            for col_name, sqlite_type, pg_type in _COLUMNS:
                if col_name in existing:
                    continue
                if dialect == "sqlite":
                    conn.execute(
                        text(f"ALTER TABLE {_TABLE} ADD COLUMN {col_name} {sqlite_type}")
                    )
                else:
                    qcol = f'"{col_name}"'
                    conn.execute(
                        text(
                            f"ALTER TABLE {quoted_table} ADD COLUMN {qcol} {pg_type}"
                        )
                    )
                logger.info("[DBMigration] Added %s.%s", _TABLE, col_name)
    except (OperationalError, ProgrammingError) as exc:
        logger.warning(
            "[DBMigration] Could not ensure user language columns: %s",
            exc,
        )
