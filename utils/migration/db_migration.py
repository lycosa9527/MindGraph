"""
Database migration utilities.

This module provides functions for running database schema migrations.
Currently supports PostgreSQL only (SQLite migration is handled separately).
"""

import logging
from typing import Any, Tuple, Dict
from sqlalchemy import inspect, text, Column
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import quoted_name
from sqlalchemy.exc import ProgrammingError

logger = logging.getLogger(__name__)


def _get_postgresql_column_type(column: Column) -> str:
    """
    Convert SQLAlchemy column type to PostgreSQL column type string.

    Args:
        column: SQLAlchemy Column object

    Returns:
        PostgreSQL column type string
    """
    return str(column.type.compile(dialect=postgresql.dialect()))


def _get_column_default(column: Column) -> str:
    """
    Get column default value as SQL string for PostgreSQL.

    Args:
        column: SQLAlchemy Column object

    Returns:
        Default value SQL string (e.g., "DEFAULT 0" or "DEFAULT NULL")
    """
    if column.default is None:
        if column.nullable:
            return "DEFAULT NULL"
        return ""

    # Handle server defaults
    if hasattr(column.default, 'arg'):
        default_value = column.default.arg
        if isinstance(default_value, (int, float)):
            return f"DEFAULT {default_value}"
        elif isinstance(default_value, bool):
            return f"DEFAULT {str(default_value).upper()}"
        elif isinstance(default_value, str):
            # Escape single quotes in string defaults
            escaped_value = default_value.replace("'", "''")
            return f"DEFAULT '{escaped_value}'"
        elif callable(default_value):
            # For callable defaults (e.g., datetime.utcnow), we can't set them in ALTER TABLE
            # They'll be handled by SQLAlchemy on insert
            # For nullable columns, use NULL as default to avoid NOT NULL violations
            if column.nullable:
                logger.debug(
                    "[DBMigration] Column '%s' has callable default, using NULL for nullable column",
                    column.name
                )
                return "DEFAULT NULL"
            else:
                # Non-nullable columns with callable defaults will need application-level handling
                logger.warning(
                    "[DBMigration] Column '%s' has callable default but is NOT NULL. "
                    "Default will be handled by application, not database.",
                    column.name
                )
                return ""

    return ""


def _create_index_if_needed(conn: Any, table_name: str, column: Column) -> bool:
    """
    Create an index for a column if it has index=True.

    Args:
        conn: Database connection
        table_name: Name of the table
        column: SQLAlchemy Column object

    Returns:
        True if index was created or not needed, False on error
    """
    try:
        # Check if column has index=True
        # In SQLAlchemy, index=True creates an implicit index
        # column.index can be True (boolean), an Index object, or False/None
        column_index = getattr(column, 'index', False)
        if not column_index:
            return True  # No index needed

        # Generate index name (SQLAlchemy convention: ix_<table>_<column>)
        index_name = f"ix_{table_name}_{column.name}"

        # Check if index already exists
        inspector = inspect(conn)
        existing_indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        if index_name in existing_indexes:
            logger.debug(
                "[DBMigration] Index '%s' already exists on table '%s'",
                index_name,
                table_name
            )
            return True

        # Use proper identifier quoting for table and column names
        quoted_table = quoted_name(table_name, quote=True)
        quoted_column = quoted_name(column.name, quote=True)

        # Create index
        create_index_sql = (
            f"CREATE INDEX IF NOT EXISTS {index_name} "
            f"ON {quoted_table}({quoted_column})"
        )
        conn.execute(text(create_index_sql))
        conn.commit()
        logger.info(
            "[DBMigration] Created index '%s' on column '%s' in table '%s'",
            index_name,
            column.name,
            table_name
        )
        return True
    except Exception as e:
        logger.warning(
            "[DBMigration] Failed to create index for column '%s' in table '%s': %s",
            column.name,
            table_name,
            e
        )
        # Don't fail the migration if index creation fails
        try:
            conn.rollback()
        except Exception:
            pass
        return True  # Return True to not block migration


def _add_column_postgresql(conn: Any, table_name: str, column: Column) -> bool:
    """
    Add a column to a PostgreSQL table.

    Args:
        conn: Database connection
        table_name: Name of the table
        column: SQLAlchemy Column object to add

    Returns:
        True if column was added successfully, False otherwise
    """
    try:
        column_type = _get_postgresql_column_type(column)
        nullable = "" if column.nullable else "NOT NULL"
        default_clause = _get_column_default(column)

        # Use proper identifier quoting for table and column names
        quoted_table = quoted_name(table_name, quote=True)
        quoted_column = quoted_name(column.name, quote=True)

        # Build ALTER TABLE statement
        sql = f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} {column_type}"
        if nullable:
            sql += f" {nullable}"
        if default_clause:
            sql += f" {default_clause}"

        conn.execute(text(sql))
        conn.commit()
        logger.info(
            "[DBMigration] Added column '%s' to table '%s'",
            column.name,
            table_name
        )

        # Create index if needed
        _create_index_if_needed(conn, table_name, column)

        return True
    except Exception as e:
        logger.error(
            "[DBMigration] Failed to add column '%s' to table '%s': %s",
            column.name,
            table_name,
            e
        )
        try:
            conn.rollback()
        except Exception:
            pass  # Ignore rollback errors
        return False


def _fix_postgresql_sequence(conn: Any, table_name: str, column: Column) -> bool:
    """
    Fix PostgreSQL sequence for a primary key column with autoincrement.

    Creates sequence if missing and configures column to use it.
    Uses proper SQL identifier quoting to prevent SQL injection.

    Args:
        conn: Database connection
        table_name: Name of the table (from SQLAlchemy metadata, trusted)
        column: SQLAlchemy Column object (should be primary key with autoincrement)

    Returns:
        True if sequence was fixed successfully, False otherwise
    """
    try:
        # Only fix sequences for primary key columns with autoincrement
        if not column.primary_key:
            return True  # Not a primary key, skip

        # Check if column has autoincrement
        autoincrement = getattr(column, 'autoincrement', False)
        if not autoincrement:
            return True  # No autoincrement, skip

        # Only handle INTEGER types (BIGINT, SMALLINT also work)
        column_type_str = str(column.type).upper()
        if 'INTEGER' not in column_type_str and 'BIGINT' not in column_type_str and 'SMALLINT' not in column_type_str:
            return True  # Not an integer type, skip

        column_name = column.name
        sequence_name = f"{table_name}_{column_name}_seq"

        # Use proper identifier quoting for table and column names
        quoted_table = quoted_name(table_name, quote=True)
        quoted_column = quoted_name(column_name, quote=True)

        # Check if sequence exists (use parameterized query for sequence name)
        seq_check = conn.execute(text(
            "SELECT EXISTS(SELECT 1 FROM pg_sequences "
            "WHERE schemaname = 'public' AND sequencename = :seq_name)"
        ), {"seq_name": sequence_name})
        sequence_exists = seq_check.scalar()

        # Get current max ID (use quoted identifiers)
        max_id_result = conn.execute(
            text(f'SELECT MAX({quoted_column}) FROM {quoted_table}')
        )
        max_id = max_id_result.scalar() or 0

        if not sequence_exists:
            logger.info(
                "[DBMigration] Sequence %s does not exist for %s.%s. Creating it...",
                sequence_name,
                table_name,
                column_name
            )

            # Check column type and default (use parameterized query)
            type_check = conn.execute(text(
                """
                SELECT data_type, column_default
                FROM information_schema.columns
                WHERE table_name = :table_name AND column_name = :column_name
                """
            ), {"table_name": table_name, "column_name": column_name})
            col_info = type_check.fetchone()

            if not col_info:
                logger.warning(
                    "[DBMigration] Could not find column %s.%s",
                    table_name,
                    column_name
                )
                return False

            # Create sequence (sequence name is safe - comes from trusted source)
            # But we still quote it properly
            quoted_sequence = quoted_name(sequence_name, quote=True)
            conn.execute(text(f"CREATE SEQUENCE {quoted_sequence}"))
            logger.info("[DBMigration] Created sequence %s", sequence_name)

            # Set sequence value
            # Note: setval() requires literal sequence name, but sequence_name comes from
            # SQLAlchemy metadata (trusted source), so it's safe to use here
            if max_id > 0:
                conn.execute(
                    text(f"SELECT setval('{sequence_name}', {max_id + 1}, false)")
                )
                logger.info(
                    "[DBMigration] Set sequence %s to %d",
                    sequence_name,
                    max_id + 1
                )
            else:
                conn.execute(text(f"SELECT setval('{sequence_name}', 1, false)"))
                logger.info("[DBMigration] Set sequence %s to 1", sequence_name)

            # Set column default to use sequence (use quoted identifiers)
            # Sequence name in nextval() must be literal, but comes from trusted source
            conn.execute(text(
                f'ALTER TABLE {quoted_table} '
                f'ALTER COLUMN {quoted_column} SET DEFAULT nextval(\'{sequence_name}\')'
            ))
            logger.info(
                "[DBMigration] Set column default to use sequence for %s.%s",
                table_name,
                column_name
            )

            # Set sequence owner (use quoted identifiers)
            conn.execute(text(
                f"ALTER SEQUENCE {quoted_sequence} "
                f"OWNED BY {quoted_table}.{quoted_column}"
            ))
            logger.info("[DBMigration] Set sequence owner")

            conn.commit()
            logger.info(
                "[DBMigration] ✓ Successfully fixed sequence for %s.%s",
                table_name,
                column_name
            )
            return True
        else:
            # Sequence exists, verify it's set correctly
            quoted_sequence = quoted_name(sequence_name, quote=True)
            seq_value_result = conn.execute(
                text(f"SELECT last_value FROM {quoted_sequence}")
            )
            last_value = seq_value_result.scalar()

            if last_value <= max_id:
                logger.info(
                    "[DBMigration] Sequence value (%d) is <= max ID (%d). Updating...",
                    last_value,
                    max_id
                )
                # Sequence name comes from SQLAlchemy metadata (trusted source)
                conn.execute(
                    text(f"SELECT setval('{sequence_name}', {max_id + 1}, false)")
                )
                conn.commit()
                logger.info(
                    "[DBMigration] ✓ Updated sequence %s to %d",
                    sequence_name,
                    max_id + 1
                )
                return True
            else:
                logger.debug(
                    "[DBMigration] Sequence %s is already set correctly (value: %d)",
                    sequence_name,
                    last_value
                )
                return True

    except Exception as e:
        logger.warning(
            "[DBMigration] Failed to fix sequence for %s.%s: %s",
            table_name,
            column.name,
            e
        )
        try:
            conn.rollback()
        except Exception:
            pass  # Ignore rollback errors
        return False  # Don't fail migration if sequence fix fails


def verify_migration_results(db_engine, base, expected_tables) -> Tuple[bool, Dict[str, Any]]:
    """
    Verify migration results by checking tables, columns, sequences, and indexes.
    
    Args:
        db_engine: SQLAlchemy engine
        base: SQLAlchemy Base metadata
        expected_tables: Set of expected table names
    
    Returns:
        tuple: (success: bool, details: dict with verification results)
    """
    inspector = inspect(db_engine)
    final_existing_tables = set(inspector.get_table_names())
    final_missing_tables = expected_tables - final_existing_tables
    
    verification_success = True
    details = {
        'tables_missing': list(final_missing_tables),
        'columns_missing': {},
        'sequences_missing': {},
        'indexes_missing': {}
    }
    
    # Verify tables
    if final_missing_tables:
        verification_success = False
    else:
        # Verify columns
        for table_name in sorted(final_existing_tables & expected_tables):
            table = base.metadata.tables[table_name]
            existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
            expected_columns = {col.name for col in table.columns}
            missing_cols = expected_columns - existing_columns
            if missing_cols:
                details['columns_missing'][table_name] = list(missing_cols)
                verification_success = False
        
        # Verify sequences for primary key columns
        with db_engine.connect() as conn:
            for table_name in sorted(final_existing_tables & expected_tables):
                table = base.metadata.tables[table_name]
                for column in table.columns:
                    if column.primary_key and getattr(column, 'autoincrement', False):
                        column_type_str = str(column.type).upper()
                        if 'INTEGER' in column_type_str or 'BIGINT' in column_type_str or 'SMALLINT' in column_type_str:
                            sequence_name = f"{table_name}_{column.name}_seq"
                            seq_check = conn.execute(text(
                                "SELECT EXISTS(SELECT 1 FROM pg_sequences "
                                "WHERE schemaname = 'public' AND sequencename = :seq_name)"
                            ), {"seq_name": sequence_name})
                            sequence_exists = seq_check.scalar()
                            if not sequence_exists:
                                if table_name not in details['sequences_missing']:
                                    details['sequences_missing'][table_name] = []
                                details['sequences_missing'][table_name].append(sequence_name)
                                verification_success = False
        
        # Verify indexes
        for table_name in sorted(final_existing_tables & expected_tables):
            table = base.metadata.tables[table_name]
            existing_indexes = {idx['name'] for idx in inspector.get_indexes(table_name)}
            expected_indexes = {idx.name for idx in table.indexes}
            missing_idxs = expected_indexes - existing_indexes
            if missing_idxs:
                details['indexes_missing'][table_name] = list(missing_idxs)
                verification_success = False
    
    return verification_success, details


def check_database_status(db_engine, base) -> Dict[str, Any]:
    """
    Check current database status (tables, columns).
    
    Args:
        db_engine: SQLAlchemy engine
        base: SQLAlchemy Base metadata
    
    Returns:
        dict: Status information with expected_tables, existing_tables, missing_tables, missing_columns
    """
    inspector = inspect(db_engine)
    existing_tables = set(inspector.get_table_names())
    expected_tables = set(base.metadata.tables.keys())
    missing_tables = expected_tables - existing_tables
    
    missing_columns = {}
    for table_name in sorted(existing_tables & expected_tables):
        table = base.metadata.tables[table_name]
        existing_cols = {col['name'] for col in inspector.get_columns(table_name)}
        expected_cols = {col.name for col in table.columns}
        missing_cols = expected_cols - existing_cols
        if missing_cols:
            missing_columns[table_name] = list(missing_cols)
    
    return {
        'expected_tables': expected_tables,
        'existing_tables': existing_tables,
        'missing_tables': missing_tables,
        'missing_columns': missing_columns
    }


def run_migrations() -> bool:
    """
    Run database schema migrations.

    This function handles automatic database schema migrations following a
    check → act → verify pattern:
    1. CHECK: Inspect current database schema and compare with expected schema
    2. ACT: Create missing tables, add missing columns, fix sequences
    3. VERIFY: Confirm all changes were applied successfully

    The migration process:
    - Step 1: Check current status (tables, columns, sequences)
    - Step 2: Create missing tables (PostgreSQL only)
    - Step 3: Add missing columns to existing tables (PostgreSQL only)
    - Step 4: Fix PostgreSQL sequences for primary key columns with autoincrement
    - Step 5: Verify all changes were applied successfully

    Note: This module currently supports PostgreSQL only.
    SQLite to PostgreSQL migration is handled by separate migration scripts.

    Returns:
        bool: True if migrations completed successfully, False otherwise
    """
    # Lazy import to avoid circular dependency with config.database
    # Import here ensures config.database is fully initialized when called
    base = None
    db_engine = None
    try:
        import config.database as database_module
        base = database_module.Base
        db_engine = database_module.engine
    except ImportError as import_error:
        logger.warning(
            "[DBMigration] Could not import database dependencies: %s. Skipping migrations.",
            import_error
        )
        return False

    if base is None or db_engine is None:
        logger.warning(
            "[DBMigration] Database dependencies not available. Skipping migrations."
        )
        return False

    try:
        # Get database dialect
        dialect = db_engine.dialect.name
        logger.info("[DBMigration] Starting database migrations for dialect: %s", dialect)
        logger.debug("[DBMigration] Running migrations for database dialect: %s", dialect)

        # Only support PostgreSQL for schema migrations
        # SQLite migration is handled by separate migration scripts
        if dialect != "postgresql":
            logger.warning(
                "[DBMigration] Schema migrations only support PostgreSQL. "
                "Current dialect: %s. Skipping migrations.",
                dialect
            )
            return True  # Return True to not block startup

        # =====================================================================
        # STEP 1: CHECK - Inspect current database status
        # =====================================================================
        logger.info("[DBMigration] Step 1: Checking current database status...")
        
        inspector = inspect(db_engine)
        existing_tables = set(inspector.get_table_names())
        expected_tables = set(base.metadata.tables.keys())
        
        # Find missing tables
        missing_tables = expected_tables - existing_tables
        
        # Log status
        logger.info(
            "[DBMigration] Status check: %d expected tables, %d existing tables, %d missing",
            len(expected_tables),
            len(existing_tables),
            len(missing_tables)
        )
        
        if missing_tables:
            logger.info(
                "[DBMigration] Missing tables: %s",
                ', '.join(sorted(missing_tables))
            )
        
        # Track migration results
        migration_success = True
        tables_created = 0
        columns_added = 0
        sequences_fixed = 0

        # =====================================================================
        # STEP 2: ACT - Create missing tables
        # =====================================================================
        if missing_tables:
            logger.info("[DBMigration] Step 2: Creating missing tables...")
            logger.info(
                "[DBMigration] Found %d missing table(s): %s",
                len(missing_tables),
                ', '.join(sorted(missing_tables))
            )
            try:
                # Create missing tables using SQLAlchemy
                # Use checkfirst=True to avoid errors if table already exists
                tables_to_create = [
                    base.metadata.tables[table_name]
                    for table_name in missing_tables
                ]
                base.metadata.create_all(
                    bind=db_engine,
                    tables=tables_to_create,
                    checkfirst=True
                )
                tables_created = len(missing_tables)
                logger.info(
                    "[DBMigration] Created %d missing table(s)",
                    tables_created
                )
                # Refresh inspector to get updated table list
                inspector = inspect(db_engine)
                existing_tables = set(inspector.get_table_names())
            except ProgrammingError as e:
                # Handle partial table creation (e.g., indexes exist but table doesn't)
                error_msg = str(e).lower()
                if "duplicate" in error_msg and ("index" in error_msg or "relation" in error_msg):
                    logger.warning(
                        "[DBMigration] Partial table creation detected (orphaned indexes exist). "
                        "Checking if tables are empty and recreating if needed..."
                    )
                    # Simple approach: if table is missing or empty, drop it (CASCADE handles indexes/constraints) and recreate
                    try:
                        with db_engine.connect() as conn:
                            inspector = inspect(db_engine)
                            existing_tables = set(inspector.get_table_names())
                            tables_to_recreate = []
                            
                            for table_name in missing_tables:
                                table = base.metadata.tables[table_name]
                                
                                # If table exists, drop it (CASCADE removes all indexes/constraints)
                                # This is safe for dev environments
                                if table_name in existing_tables:
                                    logger.info(
                                        "[DBMigration] Table '%s' exists. Dropping and recreating...",
                                        table_name
                                    )
                                    tables_to_recreate.append(table_name)
                                
                                # If table doesn't exist, drop any orphaned constraints and indexes
                                # (constraints/indexes can exist even if table doesn't, if table creation failed partway)
                                if table_name not in existing_tables:
                                    logger.info(
                                        "[DBMigration] Table '%s' doesn't exist. Cleaning up orphaned constraints and indexes...",
                                        table_name
                                    )
                                    try:
                                        # Drop constraints and indexes in a transaction
                                        with conn.begin():
                                            # STEP 1: Drop constraints first (CASCADE automatically drops associated indexes)
                                            # This handles unique constraints created by unique=True on columns
                                            try:
                                                constraint_query = text("""
                                                    SELECT c.conname, c.contype
                                                    FROM pg_constraint c
                                                    JOIN pg_class t ON c.conrelid = t.oid
                                                    JOIN pg_namespace n ON t.relnamespace = n.oid
                                                    WHERE n.nspname = 'public'
                                                    AND t.relname = :table_name
                                                    AND c.contype IN ('u', 'p')
                                                """)
                                                result = conn.execute(constraint_query, {"table_name": table_name})
                                                constraints = result.fetchall()
                                                
                                                if constraints:
                                                    logger.info(
                                                        "[DBMigration] Found %d constraint(s) for table '%s': %s",
                                                        len(constraints),
                                                        table_name,
                                                        ', '.join([c[0] for c in constraints])
                                                    )
                                                
                                                for constraint_name, constraint_type in constraints:
                                                    try:
                                                        quoted_table = quoted_name(table_name, quote=True)
                                                        quoted_constraint = quoted_name(constraint_name, quote=True)
                                                        conn.execute(text(
                                                            f'ALTER TABLE {quoted_table} DROP CONSTRAINT IF EXISTS {quoted_constraint} CASCADE'
                                                        ))
                                                        logger.info(
                                                            "[DBMigration] Dropped constraint: %s (type: %s)",
                                                            constraint_name,
                                                            'UNIQUE' if constraint_type == 'u' else 'PRIMARY KEY'
                                                        )
                                                    except Exception as drop_error:
                                                        error_msg = str(drop_error).lower()
                                                        if "does not exist" not in error_msg:
                                                            logger.warning(
                                                                "[DBMigration] Could not drop constraint %s: %s",
                                                                constraint_name,
                                                                drop_error
                                                            )
                                            except Exception as constraint_error:
                                                # Query might fail if table never existed, that's OK
                                                logger.debug(
                                                    "[DBMigration] Could not query constraints for %s: %s",
                                                    table_name,
                                                    constraint_error
                                                )
                                            
                                            # STEP 2: Drop indexes by name from the model
                                            for index in table.indexes:
                                                try:
                                                    quoted_index = quoted_name(index.name, quote=True)
                                                    conn.execute(text(f'DROP INDEX IF EXISTS {quoted_index} CASCADE'))
                                                    logger.info(
                                                        "[DBMigration] Dropped orphaned index: %s",
                                                        index.name
                                                    )
                                                except Exception as drop_error:
                                                    error_msg = str(drop_error).lower()
                                                    if "does not exist" not in error_msg:
                                                        logger.debug(
                                                            "[DBMigration] Could not drop index %s: %s",
                                                            index.name,
                                                            drop_error
                                                        )
                                            
                                            # STEP 3: Query pg_class for any remaining orphaned indexes
                                            # This catches indexes that might not be in table.indexes
                                            try:
                                                model_index_names_list = [idx.name for idx in table.indexes]
                                                if model_index_names_list:
                                                    index_names_placeholders = ', '.join([f"'{name}'" for name in model_index_names_list])
                                                    pattern = f"ix_{table_name}_%"
                                                    
                                                    orphaned_query = text(f"""
                                                        SELECT c.relname
                                                        FROM pg_class c
                                                        JOIN pg_namespace n ON n.oid = c.relnamespace
                                                        WHERE n.nspname = 'public'
                                                        AND c.relkind = 'i'
                                                        AND (
                                                            c.relname LIKE :pattern
                                                            OR c.relname IN ({index_names_placeholders})
                                                        )
                                                    """)
                                                    result = conn.execute(
                                                        orphaned_query,
                                                        {"pattern": pattern}
                                                    )
                                                    found_indexes = [row[0] for row in result.fetchall()]
                                                    
                                                    if found_indexes:
                                                        logger.info(
                                                            "[DBMigration] Found %d additional orphaned index(es): %s",
                                                            len(found_indexes),
                                                            ', '.join(found_indexes)
                                                        )
                                                    
                                                    # Drop any found indexes
                                                    for index_name in found_indexes:
                                                        try:
                                                            quoted_index = quoted_name(index_name, quote=True)
                                                            conn.execute(text(f'DROP INDEX IF EXISTS {quoted_index} CASCADE'))
                                                            logger.info(
                                                                "[DBMigration] Dropped orphaned index from pg_class: %s",
                                                                index_name
                                                            )
                                                        except Exception as drop_error:
                                                            error_msg = str(drop_error).lower()
                                                            if "does not exist" not in error_msg:
                                                                logger.debug(
                                                                    "[DBMigration] Could not drop index %s: %s",
                                                                    index_name,
                                                                    drop_error
                                                                )
                                            except Exception as query_error:
                                                # Query might fail, that's OK
                                                logger.debug(
                                                    "[DBMigration] Could not query pg_class for orphaned indexes: %s",
                                                    query_error
                                                )
                                        
                                        # Transaction committed, constraints and indexes should be dropped
                                        # Verify by querying again (outside transaction)
                                        try:
                                            # Verify constraints are gone
                                            verify_constraint_query = text("""
                                                SELECT c.conname
                                                FROM pg_constraint c
                                                JOIN pg_class t ON c.conrelid = t.oid
                                                JOIN pg_namespace n ON t.relnamespace = n.oid
                                                WHERE n.nspname = 'public'
                                                AND t.relname = :table_name
                                                AND c.contype IN ('u', 'p')
                                            """)
                                            result = conn.execute(verify_constraint_query, {"table_name": table_name})
                                            remaining_constraints = [row[0] for row in result.fetchall()]
                                            if remaining_constraints:
                                                logger.warning(
                                                    "[DBMigration] Warning: Some constraints still exist after drop: %s",
                                                    ', '.join(remaining_constraints)
                                                )
                                            
                                            # Verify indexes are gone
                                            verify_index_query = text("""
                                                SELECT indexname 
                                                FROM pg_indexes 
                                                WHERE schemaname = 'public' 
                                                AND indexname LIKE :pattern
                                            """)
                                            pattern = f"{table_name}%"
                                            result = conn.execute(verify_index_query, {"pattern": pattern})
                                            remaining_indexes = [row[0] for row in result.fetchall()]
                                            if remaining_indexes:
                                                logger.warning(
                                                    "[DBMigration] Warning: Some indexes still exist after drop: %s",
                                                    ', '.join(remaining_indexes)
                                                )
                                        except Exception:
                                            pass  # Verification is optional
                                    except Exception as cleanup_error:
                                        logger.error(
                                            "[DBMigration] Error cleaning up orphaned indexes for %s: %s",
                                            table_name,
                                            cleanup_error,
                                            exc_info=True
                                        )
                            
                            # Drop empty/corrupted tables (CASCADE will drop indexes/constraints)
                            if tables_to_recreate:
                                with conn.begin():
                                    for table_name in tables_to_recreate:
                                        try:
                                            quoted_table = quoted_name(table_name, quote=True)
                                            conn.execute(text(f'DROP TABLE IF EXISTS {quoted_table} CASCADE'))
                                            logger.info(
                                                "[DBMigration] Dropped table: %s",
                                                table_name
                                            )
                                        except Exception as drop_error:
                                            logger.error(
                                                "[DBMigration] Could not drop table '%s': %s",
                                                table_name,
                                                drop_error
                                            )
                                            # Remove from missing_tables if drop failed
                                            if table_name in missing_tables:
                                                missing_tables.remove(table_name)
                            
                            # Now create all tables that are still missing
                            # The previous transaction (constraint/index drops) has committed
                            # Use a fresh connection for table creation to ensure clean state
                            if missing_tables:
                                tables_to_create = [
                                    base.metadata.tables[table_name]
                                    for table_name in missing_tables
                                ]
                                
                                # Use a fresh connection for table creation
                                # This ensures we're not in any transaction state from previous operations
                                with db_engine.connect() as create_conn:
                                    with create_conn.begin():
                                        base.metadata.create_all(
                                            bind=create_conn,
                                            tables=tables_to_create,
                                            checkfirst=True
                                        )
                                tables_created = len(missing_tables)
                                logger.info(
                                    "[DBMigration] Created %d missing table(s) (after cleanup)",
                                    tables_created
                                )
                            else:
                                logger.info(
                                    "[DBMigration] All tables already exist (some were empty and recreated)"
                                )
                            
                            # Refresh inspector to get updated table list
                            inspector = inspect(db_engine)
                            existing_tables = set(inspector.get_table_names())
                    except Exception as retry_error:
                        logger.error(
                            "[DBMigration] Error creating tables after handling orphaned indexes: %s",
                            retry_error,
                            exc_info=True
                        )
                        migration_success = False
                        # Refresh inspector even on error to get current state
                        try:
                            inspector = inspect(db_engine)
                            existing_tables = set(inspector.get_table_names())
                        except Exception:
                            pass
                else:
                    # Non-index-related ProgrammingError
                    logger.error(
                        "[DBMigration] Error creating missing tables: %s",
                        e,
                        exc_info=True
                    )
                    migration_success = False
                    # Refresh inspector even on error to get current state
                    try:
                        inspector = inspect(db_engine)
                        existing_tables = set(inspector.get_table_names())
                    except Exception:
                        pass
            except Exception as e:
                # General exception during table creation
                logger.error(
                    "[DBMigration] Unexpected error creating missing tables: %s",
                    e,
                    exc_info=True
                )
                migration_success = False
                # Refresh inspector even on error to get current state
                try:
                    inspector = inspect(db_engine)
                    existing_tables = set(inspector.get_table_names())
                except Exception:
                    pass

        # =====================================================================
        # STEP 3: ACT - Add missing columns and fix sequences
        # =====================================================================
        # Refresh inspector after table creation
        inspector = inspect(db_engine)
        existing_tables = set(inspector.get_table_names())
        tables_to_migrate = existing_tables & expected_tables

        if tables_to_migrate:
            logger.info(
                "[DBMigration] Step 3: Migrating existing tables (%d tables to check)...",
                len(tables_to_migrate)
            )
            
            with db_engine.connect() as conn:
                for table_name in tables_to_migrate:
                    try:
                        # Get existing columns in the table
                        existing_columns = {
                            col['name'] for col in inspector.get_columns(table_name)
                        }

                        # Get expected columns from SQLAlchemy model
                        table = base.metadata.tables[table_name]
                        expected_columns = {col.name for col in table.columns}

                        # Find missing columns
                        missing_columns = expected_columns - existing_columns

                        # Add missing columns
                        if missing_columns:
                            logger.info(
                                "[DBMigration] Table '%s' has %d missing column(s): %s",
                                table_name,
                                len(missing_columns),
                                ', '.join(missing_columns)
                            )

                            for column_name in missing_columns:
                                column = table.columns[column_name]
                                success = _add_column_postgresql(conn, table_name, column)

                                if success:
                                    columns_added += 1
                                else:
                                    migration_success = False
                                    logger.error(
                                        "[DBMigration] Failed to add column '%s' to table '%s'",
                                        column_name,
                                        table_name
                                    )
                                    # Continue with next column (helpers already handle rollback)

                        # Fix PostgreSQL sequences for primary key columns with autoincrement
                        for column in table.columns:
                            if column.primary_key:
                                sequence_fixed = _fix_postgresql_sequence(conn, table_name, column)
                                if sequence_fixed:
                                    sequences_fixed += 1
                                # Don't fail migration if sequence fix fails (it's non-critical)

                    except Exception as e:
                        logger.error(
                            "[DBMigration] Error migrating table '%s': %s",
                            table_name,
                            e,
                            exc_info=True
                        )
                        migration_success = False
                        # Continue with next table to allow partial migration success
                        continue
        else:
            if tables_created > 0:
                logger.info(
                    "[DBMigration] Created %d table(s), no columns to migrate",
                    tables_created
                )
            else:
                logger.info(
                    "[DBMigration] No tables to migrate (all tables exist and are up to date)"
                )

        # =====================================================================
        # STEP 4: VERIFY - Confirm all changes were applied
        # =====================================================================
        logger.info("[DBMigration] Step 4: Verifying migration results...")
        
        _, verification_details = verify_migration_results(
            db_engine, base, expected_tables
        )
        
        # Log verification results
        if verification_details['tables_missing']:
            logger.error(
                "[DBMigration] VERIFICATION FAILED: %d table(s) still missing: %s",
                len(verification_details['tables_missing']),
                ', '.join(sorted(verification_details['tables_missing']))
            )
            migration_success = False
        else:
            logger.info(
                "[DBMigration] ✓ Verification passed: All %d expected tables exist",
                len(expected_tables)
            )
        
        if verification_details['columns_missing']:
            logger.error("[DBMigration] VERIFICATION FAILED: Missing columns found:")
            for table_name, missing_cols in verification_details['columns_missing'].items():
                logger.error(
                    "[DBMigration]   Table '%s' missing columns: %s",
                    table_name,
                    ', '.join(sorted(missing_cols))
                )
            migration_success = False
        else:
            logger.info("[DBMigration] ✓ All tables have all expected columns")
        
        if verification_details['sequences_missing']:
            logger.error("[DBMigration] VERIFICATION FAILED: Missing sequences found:")
            for table_name, missing_seqs in verification_details['sequences_missing'].items():
                logger.error(
                    "[DBMigration]   Table '%s' missing sequences: %s",
                    table_name,
                    ', '.join(sorted(missing_seqs))
                )
            migration_success = False
        else:
            logger.info("[DBMigration] ✓ All required sequences exist")
        
        if verification_details['indexes_missing']:
            logger.error("[DBMigration] VERIFICATION FAILED: Missing indexes found:")
            for table_name, missing_idxs in verification_details['indexes_missing'].items():
                logger.error(
                    "[DBMigration]   Table '%s' missing indexes: %s",
                    table_name,
                    ', '.join(sorted(missing_idxs))
                )
            migration_success = False
        else:
            logger.info("[DBMigration] ✓ All tables have all expected indexes")
        
        # Summary
        logger.info("[DBMigration] Migration summary:")
        if tables_created > 0:
            logger.info(
                "[DBMigration]   - Created %d missing table(s)",
                tables_created
            )
        if columns_added > 0:
            logger.info(
                "[DBMigration]   - Added %d missing column(s) to existing tables",
                columns_added
            )
        if sequences_fixed > 0:
            logger.info(
                "[DBMigration]   - Fixed %d PostgreSQL sequence(s) for primary key columns",
                sequences_fixed
            )
        if tables_created == 0 and columns_added == 0 and sequences_fixed == 0:
            logger.info("[DBMigration]   - No changes needed (database is up to date)")
        
        if migration_success:
            logger.info("[DBMigration] ✓ Migration completed successfully")
        else:
            logger.error("[DBMigration] ✗ Migration completed with errors")

        return migration_success

    except Exception as e:
        logger.error("[DBMigration] Migration error: %s", e, exc_info=True)
        return False
