"""
Ensure ``diagrams.workshop_visibility`` column exists.

``run_migrations()`` only applies ORM-driven column adds on PostgreSQL.
SQLite dev databases skip that path, so we add the column explicitly when
missing. PostgreSQL also runs this as a defensive fallback if a DB was
partially migrated.
"""

import logging
from typing import Set

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError

logger = logging.getLogger(__name__)

_TABLE = "diagrams"
_COLUMN = "workshop_visibility"
_INDEX = "ix_diagrams_workshop_visibility"


def _existing_column_names(engine: Engine, table_name: str) -> Set[str]:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return set()
    return {col["name"] for col in inspector.get_columns(table_name)}


def ensure_diagram_workshop_visibility_column(engine: Engine) -> None:
    """
    Add ``workshop_visibility`` (and index) on ``diagrams`` when absent.

    Idempotent: no-op if the column already exists.
    """
    try:
        columns = _existing_column_names(engine, _TABLE)
        if not columns:
            return
        if _COLUMN in columns:
            return

        dialect = engine.dialect.name
        if dialect not in ("sqlite", "postgresql"):
            logger.debug(
                "[DBMigration] workshop_visibility: skip dialect %s",
                dialect,
            )
            return

        quoted_table = f'"{_TABLE}"' if dialect == "postgresql" else _TABLE
        quoted_col = f'"{_COLUMN}"' if dialect == "postgresql" else _COLUMN

        with engine.begin() as conn:
            if dialect == "sqlite":
                conn.execute(
                    text(
                        f"ALTER TABLE {_TABLE} ADD COLUMN {_COLUMN} VARCHAR(32)"
                    )
                )
            else:
                conn.execute(
                    text(
                        f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_col} "
                        f"VARCHAR(32) NULL"
                    )
                )

            idx_sql = (
                f"CREATE INDEX IF NOT EXISTS {_INDEX} ON {_TABLE} ({_COLUMN})"
                if dialect == "sqlite"
                else (
                    f"CREATE INDEX IF NOT EXISTS {_INDEX} ON {quoted_table} "
                    f"({quoted_col})"
                )
            )
            conn.execute(text(idx_sql))

        logger.info(
            "[DBMigration] Added %s.%s (+ index)", _TABLE, _COLUMN
        )
    except (OperationalError, ProgrammingError, SQLAlchemyError) as exc:
        logger.warning(
            "[DBMigration] Could not ensure %s.%s: %s",
            _TABLE,
            _COLUMN,
            exc,
        )
