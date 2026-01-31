"""
PostgreSQL Schema Migration Utilities

This package contains utilities for PostgreSQL schema migrations:
- Creating missing tables
- Adding missing columns
- Fixing sequences and indexes
"""

from .schema_migration import run_migrations, check_database_status, verify_migration_results
from .schema_helpers import (
    add_column_postgresql,
    create_table_indexes,
    fix_postgresql_sequence
)
from .schema_table_ops import create_missing_tables

__all__ = [
    "run_migrations",
    "check_database_status",
    "verify_migration_results",
    "add_column_postgresql",
    "create_table_indexes",
    "fix_postgresql_sequence",
    "create_missing_tables",
]
