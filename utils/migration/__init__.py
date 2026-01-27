"""
Database Migration Utilities

This package contains utilities for database migrations, including SQLite to PostgreSQL migration tools.
"""

from .db_migration import run_migrations
from .sqlite_data_migration import migrate_sqlite_to_postgresql
from .sqlite_migration_backup import (
    backup_sqlite_database,
    move_sqlite_database_to_backup
)
from .sqlite_migration_progress import MigrationProgressTracker
from .sqlite_migration_tables import (
    get_table_migration_order,
    verify_migration
)
from .sqlite_migration_utils import (
    get_sqlite_db_path,
    is_migration_completed,
    is_postgresql_empty,
    load_migration_progress,
    save_migration_progress,
    MIGRATION_MARKER_FILE
)

__all__ = [
    "run_migrations",
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
