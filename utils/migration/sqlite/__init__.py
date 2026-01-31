"""
SQLite Migration Utilities

This package contains utilities for SQLite migrations:
- Type migrations (recreating tables with correct column types)
- Backup and restore operations
- Progress tracking
- Table migration functions
- Utility functions (path detection, locks, etc.)
"""

from .type_migration import (
    detect_type_mismatches,
    recreate_table_with_correct_schema,
    types_are_compatible
)
from .migration_backup import (
    backup_sqlite_database,
    move_sqlite_database_to_backup
)
from .migration_progress import MigrationProgressTracker
from .migration_tables import (
    get_table_migration_order,
    migrate_table,
    verify_migration,
    create_migration_marker,
    reset_postgresql_sequences
)
from .migration_utils import (
    get_sqlite_db_path,
    is_migration_completed,
    load_migration_progress,
    save_migration_progress,
    clear_migration_progress,
    acquire_migration_lock,
    release_migration_lock,
    is_postgresql_empty,
    check_table_completeness,
    MIGRATION_MARKER_FILE
)

__all__ = [
    "detect_type_mismatches",
    "recreate_table_with_correct_schema",
    "types_are_compatible",
    "backup_sqlite_database",
    "move_sqlite_database_to_backup",
    "MigrationProgressTracker",
    "get_table_migration_order",
    "migrate_table",
    "verify_migration",
    "create_migration_marker",
    "reset_postgresql_sequences",
    "get_sqlite_db_path",
    "is_migration_completed",
    "load_migration_progress",
    "save_migration_progress",
    "clear_migration_progress",
    "acquire_migration_lock",
    "release_migration_lock",
    "is_postgresql_empty",
    "check_table_completeness",
    "MIGRATION_MARKER_FILE",
]
