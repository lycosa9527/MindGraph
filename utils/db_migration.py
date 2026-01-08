"""
Database Migration Manager
==========================

Automatically validates and patches database schema on startup.
Detects missing columns and adds them automatically.

Safety features:
- Creates verified backup before any changes
- Runs integrity checks before and after migration
- Supports dry-run mode to preview changes
- Verifies columns were actually added after migration

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
import re
import shutil
import sqlite3
from datetime import datetime
from typing import List, Optional, Any, Tuple
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from config.database import engine, SessionLocal

logger = logging.getLogger(__name__)

# Valid identifier pattern for table/column names (prevent SQL injection)
VALID_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


class DatabaseMigrationManager:
    """
    Manages database schema migrations automatically.
    
    Features:
    - Validates schema on startup (SQLite only)
    - Detects and adds missing columns automatically
    - Safe transaction-based migrations
    - Automatic backup before migrations (SQLite file copy)
    
    Note: SQLite only supports ADD COLUMN, not ALTER COLUMN.
    Only missing columns are added - column modifications are not supported.
    """
    
    def __init__(self, engine: Engine):
        """
        Initialize migration manager.
        
        Args:
            engine: SQLAlchemy engine
        """
        self.engine = engine
        self.inspector = inspect(engine)
        self._db_path: Optional[str] = None
        
        # Verify we're using SQLite (only supported database)
        db_url = str(self.engine.url)
        if 'sqlite' not in db_url.lower():
            logger.warning(
                f"[DBMigration] Database appears to be non-SQLite: {db_url}. "
                f"Migration manager is optimized for SQLite only. "
                f"Unexpected behavior may occur."
            )
        else:
            self._db_path = self._extract_db_path(db_url)
    
    def _extract_db_path(self, db_url: str) -> Optional[str]:
        """Extract file path from SQLite URL"""
        if db_url.startswith("sqlite:////"):
            db_path = db_url.replace("sqlite:////", "/")
        elif db_url.startswith("sqlite:///"):
            db_path = db_url.replace("sqlite:///", "")
            if db_path.startswith("./"):
                db_path = db_path[2:]
            if not os.path.isabs(db_path):
                db_path = os.path.join(os.getcwd(), db_path)
        else:
            db_path = db_url.replace("sqlite:///", "")
        return db_path
    
    def _validate_identifier(self, name: str) -> bool:
        """Validate table/column name to prevent SQL injection"""
        if not name or not VALID_IDENTIFIER_PATTERN.match(name):
            logger.error(f"[DBMigration] Invalid identifier: '{name}' - rejected for safety")
            return False
        return True
    
    def _run_integrity_check(self) -> Tuple[bool, str]:
        """Run SQLite integrity check on the database."""
        from services.database_recovery import DatabaseRecovery
        from pathlib import Path
        
        if not self._db_path:
            return False, "Database path not set"
        
        recovery = DatabaseRecovery()
        # Override the db_path with our known path
        recovery.db_path = Path(self._db_path)
        return recovery.check_integrity()
    
    def _verify_backup(self, backup_path: str) -> bool:
        """Verify that a backup file is valid and readable."""
        from services.backup_scheduler import verify_backup
        from pathlib import Path
        return verify_backup(Path(backup_path))
    
    def dry_run(self) -> List[dict]:
        """
        Preview what migrations would be applied without making changes.
        
        Returns:
            List of pending migrations with details including:
            - 'action': 'add_column' or 'type_mismatch'
            - For add_column: column details
            - For type_mismatch: expected vs actual type
        """
        pending = []
        try:
            from sqlalchemy import inspect
            fresh_inspector = inspect(self.engine)
            
            for table_name, table_class in self._get_registered_tables():
                if not table_name or not fresh_inspector.has_table(table_name):
                    continue
                
                existing_columns = {
                    col['name'].lower(): col
                    for col in fresh_inspector.get_columns(table_name)
                }
                
                if table_class is None:
                    from models.auth import Base
                    table_metadata = Base.metadata.tables.get(table_name)
                    if table_metadata is None:
                        continue
                    expected_columns = {col.name: col for col in table_metadata.columns}
                else:
                    try:
                        expected_columns = {
                            col.name: col 
                            for col in table_class.__table__.columns
                        }
                    except AttributeError:
                        continue
                
                for col_name, col_def in expected_columns.items():
                    col_name_lower = col_name.lower()
                    expected_type = self._get_sqlite_type(col_def)
                    
                    if col_name_lower not in existing_columns:
                        # Missing column
                        pending.append({
                            'action': 'add_column',
                            'table': table_name,
                            'column': col_name,
                            'type': expected_type,
                            'nullable': col_def.nullable,
                            'default': self._get_sql_default_value(col_def.default) if col_def.default else None
                        })
                    else:
                        # Column exists - check for type mismatch
                        existing_col = existing_columns[col_name_lower]
                        actual_type = str(existing_col.get('type', ''))
                        
                        if not self._types_are_compatible(expected_type, actual_type):
                            pending.append({
                                'action': 'type_mismatch',
                                'table': table_name,
                                'column': col_name,
                                'expected_type': expected_type,
                                'actual_type': actual_type,
                                'is_primary_key': col_def.primary_key
                            })
            
            return pending
        except Exception as e:
            logger.error(f"[DBMigration] Dry run failed: {e}")
            return []
        
    def validate_and_migrate(self) -> bool:
        """
        Validate database schema and apply migrations.
        
        Safety steps:
        1. Run integrity check on database
        2. Detect what changes are needed (dry-run)
        3. Create and verify backup
        4. Apply migrations (column additions and type fixes)
        5. Verify migrations were applied
        6. Run post-migration integrity check
        
        Supports:
        - Adding missing columns
        - Fixing column type mismatches (via table recreation)
        
        Returns:
            True if migration successful, False otherwise
        """
        try:
            logger.info("[DBMigration] Starting database schema validation...")
            
            # Step 1: Pre-migration integrity check
            integrity_ok, integrity_msg = self._run_integrity_check()
            if not integrity_ok:
                logger.error(f"[DBMigration] Pre-migration integrity check FAILED: {integrity_msg}")
                logger.error("[DBMigration] Aborting migration - database may be corrupt")
                return False
            logger.info(f"[DBMigration] Pre-migration integrity check: {integrity_msg}")
            
            # Step 2: Detect changes needed (missing columns and type mismatches)
            pending_migrations = self.dry_run()
            
            # Categorize migrations
            column_additions = [m for m in pending_migrations if m.get('action') == 'add_column']
            type_mismatches = [m for m in pending_migrations if m.get('action') == 'type_mismatch']
            
            if column_additions:
                logger.info(f"[DBMigration] Found {len(column_additions)} pending column addition(s):")
                for m in column_additions:
                    logger.info(f"[DBMigration]   - {m['table']}.{m['column']} ({m['type']})")
            
            if type_mismatches:
                logger.info(f"[DBMigration] Found {len(type_mismatches)} column type mismatch(es):")
                for m in type_mismatches:
                    logger.info(
                        f"[DBMigration]   - {m['table']}.{m['column']}: "
                        f"{m['actual_type']} -> {m['expected_type']}"
                        f"{' (PRIMARY KEY)' if m.get('is_primary_key') else ''}"
                    )
            
            changes_detected = len(pending_migrations) > 0
            
            # Step 3: Create and verify backup if changes needed
            backup_path = None
            if changes_detected:
                backup_path = self._create_backup()
                if not backup_path:
                    logger.error("[DBMigration] Backup creation failed - aborting migration for safety")
                    return False
                
                # Verify backup is valid before proceeding
                if not self._verify_backup(backup_path):
                    logger.error("[DBMigration] Backup verification failed - aborting migration for safety")
                    return False
                
                logger.info(f"[DBMigration] Backup created and verified: {backup_path}")
            
            # Step 4: Import all models to register them with Base
            from models.auth import Organization, User, APIKey, Base
            
            try:
                from models.token_usage import TokenUsage
                logger.debug("[DBMigration] TokenUsage model found")
            except ImportError:
                logger.debug("[DBMigration] TokenUsage model not found (okay if not implemented yet)")
                TokenUsage = None
            
            # Step 5a: Handle type mismatches first (requires table recreation)
            tables_recreated = 0
            if type_mismatches:
                # Group mismatches by table
                tables_to_recreate = {}
                for m in type_mismatches:
                    table = m['table']
                    if table not in tables_to_recreate:
                        tables_to_recreate[table] = []
                    tables_to_recreate[table].append(m)
                
                for table_name, mismatches in tables_to_recreate.items():
                    # Find the table class
                    table_class = None
                    for t_name, t_class in self._get_registered_tables():
                        if t_name == table_name:
                            table_class = t_class
                            break
                    
                    if table_class:
                        logger.info(f"[DBMigration] Recreating table '{table_name}' to fix type mismatches...")
                        if self._recreate_table_with_correct_schema(table_name, table_class, mismatches):
                            tables_recreated += 1
                        else:
                            logger.error(f"[DBMigration] Failed to recreate table '{table_name}'")
                            logger.error(f"[DBMigration] Restore from backup: {backup_path}")
                            return False
            
            # Step 5b: Apply column additions
            columns_added = 0
            for table_name, table_class in self._get_registered_tables():
                if table_name and table_class:
                    migrated = self._migrate_table(table_name, table_class)
                    if migrated:
                        columns_added += 1
            
            total_migrations = tables_recreated + columns_added
            
            # Step 6: Post-migration integrity check
            if total_migrations > 0:
                post_integrity_ok, post_integrity_msg = self._run_integrity_check()
                if not post_integrity_ok:
                    logger.error(f"[DBMigration] Post-migration integrity check FAILED: {post_integrity_msg}")
                    logger.error(f"[DBMigration] CRITICAL: Database may be corrupted!")
                    logger.error(f"[DBMigration] Restore from backup: {backup_path}")
                    return False
                logger.info(f"[DBMigration] Post-migration integrity check: {post_integrity_msg}")
                
                if tables_recreated > 0:
                    logger.info(f"[DBMigration] Recreated {tables_recreated} table(s) with correct schema")
                if columns_added > 0:
                    logger.info(f"[DBMigration] Applied {columns_added} column migration(s)")
                logger.info(f"[DBMigration] Backup available at: {backup_path}")
            else:
                logger.info("[DBMigration] Database schema is up to date - no migrations needed")
            
            return True
            
        except Exception as e:
            logger.error(f"[DBMigration] Schema validation failed: {e}", exc_info=True)
            logger.error("[DBMigration] If migration failed, restore from backup if needed")
            return False
    
    def _detect_changes(self) -> bool:
        """
        Detect if any migrations will be needed (before creating backup).
        
        Returns:
            True if changes detected, False otherwise
        """
        try:
            # Refresh inspector to avoid stale data
            from sqlalchemy import inspect
            fresh_inspector = inspect(self.engine)
            
            # Import all models to register them with Base
            from models.auth import Organization, User, APIKey, Base
            
            try:
                from models.token_usage import TokenUsage
            except ImportError:
                TokenUsage = None
            
            # Check each table for changes
            for table_name, table_class in self._get_registered_tables():
                if not table_name or not fresh_inspector.has_table(table_name):
                    continue
                
                # Get existing and expected columns (case-insensitive comparison for SQLite)
                existing_columns = {
                    col['name']: col 
                    for col in fresh_inspector.get_columns(table_name)
                }
                # Create case-insensitive lookup dict (lowercase key -> original name)
                existing_columns_lower = {
                    col['name'].lower(): col['name']
                    for col in fresh_inspector.get_columns(table_name)
                }
                
                # Get expected columns
                if table_class is None:
                    from models.auth import Base
                    table_metadata = Base.metadata.tables.get(table_name)
                    if table_metadata is None:
                        continue
                    expected_columns = {col.name: col for col in table_metadata.columns}
                else:
                    try:
                        expected_columns = {
                            col.name: col 
                            for col in table_class.__table__.columns
                        }
                    except AttributeError:
                        from models.auth import Base
                        table_metadata = Base.metadata.tables.get(table_name)
                        if table_metadata is None:
                            continue
                        expected_columns = {col.name: col for col in table_metadata.columns}
                
                # Check for missing columns (case-insensitive check for SQLite compatibility)
                for col_name in expected_columns:
                    # Check both exact match and case-insensitive match
                    if col_name not in existing_columns and col_name.lower() not in existing_columns_lower:
                        logger.debug(f"[DBMigration] Missing column detected: '{col_name}' in '{table_name}' (will add)")
                        return True
            
            return False
        except Exception as e:
            logger.warning(f"[DBMigration] Error detecting changes: {e} - will create backup anyway for safety")
            return True  # Create backup anyway if detection fails
    
    def _create_backup(self) -> Optional[str]:
        """Create a backup of the SQLite database before migration."""
        from services.backup_scheduler import backup_database_safely, BACKUP_DIR
        from pathlib import Path
        from datetime import datetime
        
        if not self._db_path:
            logger.error("[DBMigration] Database path not set - cannot create backup")
            return None
        
        source_db = Path(self._db_path)
        if not source_db.exists():
            logger.error(f"[DBMigration] Database file not found: {source_db}")
            return None
        
        # Create migration-specific backup directory
        backup_dir = source_db.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamped backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"{source_db.name}.migration_{timestamp}"
        
        # Use the robust backup function from backup_scheduler
        if backup_database_safely(source_db, backup_path):
            logger.info(f"[DBMigration] Migration backup created: {backup_path}")
            return str(backup_path)
        else:
            logger.error("[DBMigration] Backup creation failed")
            return None
    
    def _restore_from_backup(self, backup_path: str) -> bool:
        """Restore SQLite database from backup"""
        from services.database_recovery import DatabaseRecovery
        from pathlib import Path
        
        if not self._db_path:
            logger.error("[DBMigration] Database path not set - cannot restore")
            return False
        
        # Dispose engine connections before restore
        self.engine.dispose()
        
        recovery = DatabaseRecovery()
        recovery.db_path = Path(self._db_path)
        success, message = recovery.restore_from_backup(Path(backup_path))
        
        if success:
            logger.info(f"[DBMigration] {message}")
        else:
            logger.error(f"[DBMigration] Restore failed: {message}")
        
        return success
    
    def _get_registered_tables(self) -> List[tuple]:
        """Get all tables registered with Base metadata"""
        from models.auth import Base
        
        # Ensure TokenUsage is imported to register with Base metadata
        try:
            from models.token_usage import TokenUsage
        except ImportError:
            pass  # TokenUsage may not exist yet
        
        tables = []
        for table_name, table in Base.metadata.tables.items():
            # Get the model class if possible
            model_class = None
            try:
                # Try to find model class from registry
                if hasattr(Base.registry, '_class_registry'):
                    for cls in Base.registry._class_registry.values():
                        if hasattr(cls, '__tablename__') and cls.__tablename__ == table_name:
                            model_class = cls
                            break
            except Exception:
                # If registry access fails, try alternative method
                try:
                    for mapper in Base.registry.mappers:
                        if mapper.class_.__tablename__ == table_name:
                            model_class = mapper.class_
                            break
                except Exception:
                    pass
            
            tables.append((table_name, model_class))
        
        return tables
    
    def _migrate_table(self, table_name: str, model_class: Any) -> bool:
        """
        Migrate a single table - add missing columns.
        
        Args:
            table_name: Name of the table
            model_class: SQLAlchemy model class
            
        Returns:
            True if migrations were applied, False otherwise
        """
        try:
            # Refresh inspector to get latest table and column information
            from sqlalchemy import inspect
            fresh_inspector = inspect(self.engine)
            
            # Check if table exists
            if not fresh_inspector.has_table(table_name):
                logger.info(f"[DBMigration] Table '{table_name}' does not exist")
                logger.info(f"[DBMigration] Table will be created by Base.metadata.create_all() in init_db()")
                # Note: Table creation happens in init_db() via Base.metadata.create_all()
                # Migration manager only handles adding columns to existing tables
                return False
            
            # Get existing columns (case-insensitive comparison for SQLite compatibility)
            existing_columns = {
                col['name']: col 
                for col in fresh_inspector.get_columns(table_name)
            }
            # Create case-insensitive lookup dict (lowercase key -> original name)
            existing_columns_lower = {
                col['name'].lower(): col['name']
                for col in fresh_inspector.get_columns(table_name)
            }
            
            # Get expected columns from model
            if model_class is None:
                # If no model class, use metadata
                from models.auth import Base
                table_metadata = Base.metadata.tables.get(table_name)
                if table_metadata is None:
                    logger.debug(f"[DBMigration] No metadata found for table '{table_name}' - skipping")
                    return False
                expected_columns = {col.name: col for col in table_metadata.columns}
            else:
                # Use model class to get columns
                try:
                    expected_columns = {
                        col.name: col 
                        for col in model_class.__table__.columns
                    }
                except AttributeError:
                    # Fallback to metadata if __table__ not available
                    from models.auth import Base
                    table_metadata = Base.metadata.tables.get(table_name)
                    if table_metadata is None:
                        logger.debug(f"[DBMigration] No table definition found for '{table_name}' - skipping")
                        return False
                    expected_columns = {col.name: col for col in table_metadata.columns}
            
            # Find missing columns only (case-insensitive check for SQLite compatibility)
            missing_columns = []
            
            for col_name, col_def in expected_columns.items():
                # Check both exact match and case-insensitive match (SQLite columns are case-insensitive)
                if col_name not in existing_columns and col_name.lower() not in existing_columns_lower:
                    missing_columns.append((col_name, col_def))
                elif col_name.lower() in existing_columns_lower and col_name not in existing_columns:
                    # Column exists but with different case - log for debugging
                    actual_name = existing_columns_lower[col_name.lower()]
                    logger.debug(f"[DBMigration] Column '{col_name}' exists as '{actual_name}' (case difference) - skipping")
            
            # Only migrate if there are missing columns
            if not missing_columns:
                return False
            
            # Apply migrations: backup → add missing columns
            logger.info(f"[DBMigration] Table '{table_name}': Found {len(missing_columns)} missing column(s) to add")
            
            db = SessionLocal()
            try:
                # Add missing columns (SQLite supports ADD COLUMN)
                columns_added = 0
                successfully_added_columns = []  # Track which columns were actually added
                for col_name, col_def in missing_columns:
                    try:
                        if not self._add_column(table_name, col_name, col_def, db):
                            logger.error(f"[DBMigration] Skipping column '{col_name}' due to validation failure")
                            continue
                        db.commit()  # Commit each successful addition immediately
                        logger.info(f"[DBMigration] Added column '{col_name}' to table '{table_name}'")
                        columns_added += 1
                        successfully_added_columns.append(col_name)
                    except OperationalError as e:
                        # Handle duplicate column error gracefully (column might exist with different case)
                        error_msg = str(e).lower()
                        if 'duplicate column' in error_msg or 'already exists' in error_msg:
                            logger.warning(f"[DBMigration] Column '{col_name}' already exists in '{table_name}' (possibly case difference) - skipping")
                            db.rollback()  # Rollback the failed statement to clear error state
                            continue
                        else:
                            # Re-raise if it's a different OperationalError
                            db.rollback()
                            raise
                
                # Only verify if we actually added columns
                if columns_added > 0:
                    # Verify columns were actually added (safety check)
                    # Recreate inspector to see new columns
                    from sqlalchemy import inspect
                    fresh_inspector = inspect(self.engine)
                    updated_columns = {
                        col['name']: col 
                        for col in fresh_inspector.get_columns(table_name)
                    }
                    # Create case-insensitive lookup for verification
                    updated_columns_lower = {
                        col['name'].lower(): col['name']
                        for col in fresh_inspector.get_columns(table_name)
                    }
                    
                    # Verify only successfully added columns exist (case-insensitive check)
                    all_added = True
                    for col_name in successfully_added_columns:
                        # Check both exact match and case-insensitive match
                        if col_name not in updated_columns and col_name.lower() not in updated_columns_lower:
                            logger.error(f"[DBMigration] WARNING: Column '{col_name}' was not added to '{table_name}' - verification failed!")
                            all_added = False
                    
                    if all_added:
                        logger.info(f"[DBMigration] Table '{table_name}': ✅ All {columns_added} column(s) added and verified successfully")
                        return True
                    else:
                        logger.error(f"[DBMigration] Table '{table_name}': Verification failed - some columns may not have been added")
                        return False
                else:
                    # No columns were added (all were duplicates or skipped)
                    logger.debug(f"[DBMigration] Table '{table_name}': No columns needed to be added (all already exist)")
                    return False
                
            except Exception as e:
                db.rollback()
                logger.error(f"[DBMigration] Failed to migrate table '{table_name}': {e}", exc_info=True)
                # Don't raise - return False to continue with other tables
                return False
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"[DBMigration] Error migrating table '{table_name}': {e}", exc_info=True)
            return False
    
    def _add_column(self, table_name: str, column_name: str, column_def: Any, db: Session) -> bool:
        """
        Add a column to a table.
        
        Args:
            table_name: Table name
            column_name: Column name to add
            column_def: SQLAlchemy Column definition
            db: Database session
            
        Returns:
            True if column was added, False if validation failed
        """
        # Build SQLite ALTER TABLE statement
        sql = self._build_sqlite_alter_table(table_name, column_name, column_def)
        
        if sql is None:
            logger.error(f"[DBMigration] Failed to build ALTER TABLE statement for {table_name}.{column_name}")
            return False
        
        logger.debug(f"[DBMigration] Executing: {sql}")
        db.execute(text(sql))
        return True
    
    def _build_sqlite_alter_table(self, table_name: str, column_name: str, column_def: Any) -> Optional[str]:
        """
        Build ALTER TABLE statement for SQLite.
        
        SQLite has limited ALTER TABLE support - only supports:
        - ADD COLUMN
        - No DEFAULT constraints for existing tables
        - No NOT NULL without DEFAULT
        
        Args:
            table_name: Table name
            column_name: Column name
            column_def: Column definition
            
        Returns:
            SQL ALTER TABLE statement, or None if validation fails
        """
        # Validate identifiers to prevent SQL injection
        if not self._validate_identifier(table_name):
            logger.error(f"[DBMigration] Invalid table name: '{table_name}' - SQL injection protection")
            return None
        if not self._validate_identifier(column_name):
            logger.error(f"[DBMigration] Invalid column name: '{column_name}' - SQL injection protection")
            return None
        
        col_type = self._get_sqlite_type(column_def)
        nullable = "NULL" if column_def.nullable else "NOT NULL"
        
        # SQLite: Can't add NOT NULL without DEFAULT for existing tables
        if not column_def.nullable and column_def.default is None:
            nullable = "NULL"  # Make it nullable, we'll add constraint later if needed
            logger.warning(
                f"[DBMigration] Column '{column_name}' is NOT NULL but no default provided. "
                f"Making it nullable for SQLite compatibility."
            )
        
        # Add DEFAULT if specified
        default_clause = ""
        if column_def.default is not None:
            default_value = self._get_sql_default_value(column_def.default)
            if default_value:
                default_clause = f" DEFAULT {default_value}"
        
        # Use double quotes for identifiers (SQL standard)
        return f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {col_type} {nullable}{default_clause}'
    
    def _get_sqlite_type(self, column_def: Any) -> str:
        """Convert SQLAlchemy type to SQLite type"""
        from utils.db_type_migration import get_sqlite_type
        return get_sqlite_type(column_def)
    
    def _types_are_compatible(self, expected_type: str, actual_type: str) -> bool:
        """Check if expected and actual column types are compatible"""
        from utils.db_type_migration import types_are_compatible
        return types_are_compatible(expected_type, actual_type)
    
    def _recreate_table_with_correct_schema(
        self,
        table_name: str,
        table_class: Any,
        mismatches: List[dict]
    ) -> bool:
        """Recreate a table with the correct schema via table recreation"""
        from utils.db_type_migration import recreate_table_with_correct_schema
        return recreate_table_with_correct_schema(
            self._db_path, table_name, table_class, mismatches
        )
    
    def _get_sql_default_value(self, default: Any) -> Optional[str]:
        """
        Convert SQLAlchemy default to SQL value.
        
        Used when adding new columns (SQLite supports DEFAULT on new columns).
        """
        if default is None:
            return None
        
        # Handle callable defaults (e.g., datetime.utcnow)
        if callable(default):
            # For callable defaults, we can't set them in SQL
            # Return None and let application handle it
            return None
        
        # Handle ColumnDefault
        if hasattr(default, 'arg'):
            default = default.arg
            if callable(default):
                return None
        
        # Convert Python values to SQL
        if isinstance(default, bool):
            return '1' if default else '0'
        elif isinstance(default, (int, float)):
            return str(default)
        elif isinstance(default, str):
            return f"'{default}'"
        else:
            return str(default)


# Global migration manager instance
migration_manager: Optional[DatabaseMigrationManager] = None


def get_migration_manager() -> DatabaseMigrationManager:
    """Get or create migration manager instance"""
    global migration_manager
    if migration_manager is None:
        migration_manager = DatabaseMigrationManager(engine)
    return migration_manager


def run_migrations() -> bool:
    """
    Run database migrations on startup.
    
    This should be called during application initialization.
    
    Returns:
        True if migrations successful, False otherwise
    """
    try:
        manager = get_migration_manager()
        return manager.validate_and_migrate()
    except Exception as e:
        logger.error(f"[DBMigration] Failed to run migrations: {e}", exc_info=True)
        return False


def restore_from_backup(backup_path: str) -> bool:
    """
    Restore SQLite database from a backup file.
    
    Args:
        backup_path: Path to the backup file
        
    Returns:
        True if restore successful, False otherwise
        
    Example:
        from utils.db_migration import restore_from_backup
        restore_from_backup("backups/mindgraph.db.backup_20240101_120000")
    """
    try:
        manager = get_migration_manager()
        return manager._restore_from_backup(backup_path)
    except Exception as e:
        logger.error(f"[DBMigration] Restore failed: {e}", exc_info=True)
        return False


def preview_migrations() -> List[dict]:
    """
    Preview what migrations would be applied without making changes.
    
    Use this to see what will happen before running migrations.
    
    Returns:
        List of pending migrations with details:
        [{'table': 'users', 'column': 'role', 'type': 'VARCHAR(20)', ...}, ...]
        
    Example:
        from utils.db_migration import preview_migrations
        pending = preview_migrations()
        for m in pending:
            print(f"Will add: {m['table']}.{m['column']} ({m['type']})")
    """
    try:
        manager = get_migration_manager()
        return manager.dry_run()
    except Exception as e:
        logger.error(f"[DBMigration] Preview failed: {e}", exc_info=True)
        return []


def check_database_integrity() -> Tuple[bool, str]:
    """
    Run integrity check on the database.
    
    Returns:
        Tuple of (passed: bool, message: str)
        
    Example:
        from utils.db_migration import check_database_integrity
        ok, msg = check_database_integrity()
        if not ok:
            print(f"Database corrupted: {msg}")
    """
    try:
        manager = get_migration_manager()
        return manager._run_integrity_check()
    except Exception as e:
        return False, f"Integrity check error: {e}"

