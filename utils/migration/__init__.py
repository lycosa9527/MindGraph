"""
Database Migration Utilities

PostgreSQL schema management is now handled by Alembic (see ``alembic/``).
This package retains SQLite and SQLite-to-PostgreSQL data migration helpers.
"""

from .sqlite_to_postgresql import migrate_sqlite_to_postgresql
from .sqlite import (
    backup_sqlite_database,
    move_sqlite_database_to_backup,
    MigrationProgressTracker,
    get_table_migration_order,
    verify_migration,
    get_sqlite_db_path,
    is_migration_completed,
    is_postgresql_empty,
    load_migration_progress,
    save_migration_progress,
    MIGRATION_MARKER_FILE,
)

__all__ = [
    "migrate_sqlite_to_postgresql",
    "backup_sqlite_database",
    "move_sqlite_database_to_backup",
    "MigrationProgressTracker",
    "load_migration_progress",
    "save_migration_progress",
    "get_table_migration_order",
    "verify_migration",
    "get_sqlite_db_path",
    "is_migration_completed",
    "is_postgresql_empty",
    "MIGRATION_MARKER_FILE",
]
