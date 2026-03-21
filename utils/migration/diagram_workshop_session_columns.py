"""
Ensure ``diagrams`` workshop session columns exist (expires_at, started_at, preset).

PostgreSQL: usually added by ORM ``run_migrations``. SQLite needs explicit ALTER.
"""

import logging
from typing import Set

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError

logger = logging.getLogger(__name__)

_TABLE = "diagrams"
_COLUMNS = (
    ("workshop_started_at", "DATETIME", "TIMESTAMP NULL"),
    ("workshop_expires_at", "DATETIME", "TIMESTAMP NULL"),
    ("workshop_duration_preset", "VARCHAR(16)", "VARCHAR(16) NULL"),
)
_INDEX = "ix_diagrams_workshop_expires_at"


def _existing_column_names(engine: Engine, table_name: str) -> Set[str]:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return set()
    return {col["name"] for col in inspector.get_columns(table_name)}


def ensure_diagram_workshop_session_columns(engine: Engine) -> None:
    """Add workshop session columns and index on ``workshop_expires_at`` if missing."""
    try:
        columns = _existing_column_names(engine, _TABLE)
        if not columns:
            return

        dialect = engine.dialect.name
        if dialect not in ("sqlite", "postgresql"):
            logger.debug(
                "[DBMigration] workshop session cols: skip dialect %s",
                dialect,
            )
            return

        quoted_table = f'"{_TABLE}"' if dialect == "postgresql" else _TABLE

        added_any = False
        with engine.begin() as conn:
            for col_name, sqlite_type, pg_type in _COLUMNS:
                if col_name in columns:
                    continue
                if dialect == "sqlite":
                    conn.execute(
                        text(
                            f"ALTER TABLE {_TABLE} ADD COLUMN {col_name} {sqlite_type}"
                        )
                    )
                else:
                    qcol = f'"{col_name}"'
                    conn.execute(
                        text(
                            f"ALTER TABLE {quoted_table} ADD COLUMN {qcol} {pg_type}"
                        )
                    )
                added_any = True
                logger.info("[DBMigration] Added %s.%s", _TABLE, col_name)

            if dialect == "sqlite":
                conn.execute(
                    text(
                        f"CREATE INDEX IF NOT EXISTS {_INDEX} ON {_TABLE} "
                        f"(workshop_expires_at)"
                    )
                )
            else:
                conn.execute(
                    text(
                        f"CREATE INDEX IF NOT EXISTS {_INDEX} ON {quoted_table} "
                        f"(\"workshop_expires_at\")"
                    )
                )

        if added_any:
            logger.info("[DBMigration] Workshop session columns ensured on %s", _TABLE)
    except (OperationalError, ProgrammingError, SQLAlchemyError) as exc:
        logger.warning(
            "[DBMigration] Could not ensure workshop session columns: %s",
            exc,
        )
