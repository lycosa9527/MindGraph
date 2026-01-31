"""
Database Migration Utilities

This package contains utilities for database migrations, including SQLite to PostgreSQL migration tools.
"""

# Re-export from subfolders for backward compatibility
from .postgresql import (
    run_migrations,
    check_database_status,
    verify_migration_results
)
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
    MIGRATION_MARKER_FILE
)

__all__ = [
    "run_migrations",
    "check_database_status",
    "verify_migration_results",
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
