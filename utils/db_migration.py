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
        """
        Run SQLite integrity check on the database.
        
        Returns:
            Tuple of (passed: bool, message: str)
        """
        if not self._db_path or not os.path.exists(self._db_path):
            return False, "Database file not found"
        
        try:
            conn = sqlite3.connect(self._db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0] == 'ok':
                return True, "Integrity check passed"
            else:
                return False, f"Integrity check failed: {result}"
        except Exception as e:
            return False, f"Integrity check error: {e}"
    
    def _verify_backup(self, backup_path: str) -> bool:
        """
        Verify that a backup file is valid and readable.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            True if backup is valid, False otherwise
        """
        if not os.path.exists(backup_path):
            logger.error(f"[DBMigration] Backup file does not exist: {backup_path}")
            return False
        
        try:
            # Open backup and run integrity check
            conn = sqlite3.connect(backup_path, timeout=30.0)
            cursor = conn.cursor()
            
            # Check integrity
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            if not result or result[0] != 'ok':
                logger.error(f"[DBMigration] Backup integrity check failed: {result}")
                conn.close()
                return False
            
            # Verify tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            if not tables:
                logger.error("[DBMigration] Backup has no tables - invalid backup")
                conn.close()
                return False
            
            conn.close()
            logger.info(f"[DBMigration] Backup verified: {len(tables)} tables, integrity OK")
            return True
            
        except Exception as e:
            logger.error(f"[DBMigration] Backup verification failed: {e}")
            return False
    
    def dry_run(self) -> List[dict]:
        """
        Preview what migrations would be applied without making changes.
        
        Returns:
            List of pending migrations with details
        """
        pending = []
        try:
            from sqlalchemy import inspect
            fresh_inspector = inspect(self.engine)
            
            for table_name, table_class in self._get_registered_tables():
                if not table_name or not fresh_inspector.has_table(table_name):
                    continue
                
                existing_columns = {
                    col['name'].lower(): col['name']
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
                    if col_name.lower() not in existing_columns:
                        pending.append({
                            'table': table_name,
                            'column': col_name,
                            'type': self._get_sqlite_type(col_def),
                            'nullable': col_def.nullable,
                            'default': self._get_sql_default_value(col_def.default) if col_def.default else None
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
        4. Apply migrations
        5. Verify migrations were applied
        6. Run post-migration integrity check
        
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
            
            # Step 2: Detect missing columns (dry-run first)
            pending_migrations = self.dry_run()
            if pending_migrations:
                logger.info(f"[DBMigration] Found {len(pending_migrations)} pending column addition(s):")
                for m in pending_migrations:
                    logger.info(f"[DBMigration]   - {m['table']}.{m['column']} ({m['type']})")
            
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
            
            # Step 5: Apply migrations
            migrations_applied = 0
            for table_name, table_class in self._get_registered_tables():
                if table_name and table_class:
                    migrated = self._migrate_table(table_name, table_class)
                    if migrated:
                        migrations_applied += 1
            
            # Step 6: Post-migration integrity check
            if migrations_applied > 0:
                post_integrity_ok, post_integrity_msg = self._run_integrity_check()
                if not post_integrity_ok:
                    logger.error(f"[DBMigration] Post-migration integrity check FAILED: {post_integrity_msg}")
                    logger.error(f"[DBMigration] CRITICAL: Database may be corrupted!")
                    logger.error(f"[DBMigration] Restore from backup: {backup_path}")
                    return False
                logger.info(f"[DBMigration] Post-migration integrity check: {post_integrity_msg}")
                logger.info(f"[DBMigration] Applied {migrations_applied} table migration(s) successfully")
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
        """
        Create a backup of the SQLite database before migration (file copy).
        
        Returns:
            Path to backup file if successful, None otherwise
        """
        try:
            return self._backup_sqlite()
        except Exception as e:
            logger.error(f"[DBMigration] Backup creation failed: {e}", exc_info=True)
            return None
    
    def _backup_sqlite(self) -> Optional[str]:
        """Create backup for SQLite database using SQLite backup API"""
        try:
            db_path = self._db_path
            if not db_path:
                logger.error("[DBMigration] Database path not set - cannot create backup")
                return None
            
            if not os.path.exists(db_path):
                logger.error(f"[DBMigration] Database file not found: {db_path} - cannot create backup")
                return None
            
            # Create backup directory
            backup_dir = os.path.join(os.path.dirname(db_path), "backups")
            os.makedirs(backup_dir, exist_ok=True)
            
            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            db_name = os.path.basename(db_path)
            backup_name = f"{db_name}.backup_{timestamp}"
            backup_path = os.path.join(backup_dir, backup_name)
            
            # Use SQLite backup API for safe backup (handles WAL mode correctly)
            # This ensures we get a consistent snapshot even if database is in use
            source_conn = None
            backup_conn = None
            try:
                source_conn = sqlite3.connect(db_path, timeout=60.0)
                backup_conn = sqlite3.connect(backup_path, timeout=60.0)
                
                # Disable WAL mode for backup file (backups are standalone snapshots)
                backup_conn.execute("PRAGMA journal_mode=DELETE")
                
                # Use SQLite backup API - handles WAL mode correctly
                if hasattr(source_conn, 'backup'):
                    source_conn.backup(backup_conn)
                else:
                    # Fallback: dump/restore method
                    for line in source_conn.iterdump():
                        backup_conn.executescript(line)
                    backup_conn.commit()
                
                logger.info(f"[DBMigration] Database backup created: {backup_path}")
            except Exception as e:
                logger.error(f"[DBMigration] Backup failed: {e}")
                # Clean up partial backup
                if os.path.exists(backup_path):
                    try:
                        os.unlink(backup_path)
                    except Exception:
                        pass
                return None
            finally:
                if backup_conn:
                    try:
                        backup_conn.close()
                    except Exception:
                        pass
                if source_conn:
                    try:
                        source_conn.close()
                    except Exception:
                        pass
                
                # Clean up any WAL/SHM files that might have been created
                for suffix in ["-wal", "-shm"]:
                    wal_file = backup_path + suffix
                    if os.path.exists(wal_file):
                        try:
                            os.unlink(wal_file)
                        except Exception:
                            pass
            
            # Clean old backups (keep last 10)
            self._cleanup_old_backups(backup_dir, max_backups=10)
            
            return backup_path
            
        except Exception as e:
            logger.error(f"[DBMigration] SQLite backup failed: {e}", exc_info=True)
            return None
    
    def _cleanup_old_backups(self, backup_dir: str, max_backups: int = 10, pattern: str = "*.backup_*"):
        """Clean up old backup files, keeping only the most recent ones"""
        try:
            import glob
            
            backup_files = glob.glob(os.path.join(backup_dir, pattern))
            if len(backup_files) <= max_backups:
                return
            
            # Sort by modification time (newest first)
            backup_files.sort(key=os.path.getmtime, reverse=True)
            
            # Remove old backups
            for old_backup in backup_files[max_backups:]:
                try:
                    os.remove(old_backup)
                    # Also remove associated WAL and SHM files if they exist
                    for ext in ['-wal', '-shm']:
                        wal_backup = old_backup + ext
                        if os.path.exists(wal_backup):
                            os.remove(wal_backup)
                    logger.debug(f"[DBMigration] Cleaned up old backup: {old_backup}")
                except Exception as e:
                    logger.warning(f"[DBMigration] Failed to remove old backup {old_backup}: {e}")
            
        except Exception as e:
            logger.warning(f"[DBMigration] Backup cleanup failed: {e}")
    
    def _restore_from_backup(self, backup_path: str) -> bool:
        """Restore SQLite database from backup"""
        try:
            if not os.path.exists(backup_path):
                logger.error(f"[DBMigration] Backup file not found: {backup_path}")
                return False
            
            db_url = str(self.engine.url)
            if db_url.startswith("sqlite:///"):
                db_path = db_url.replace("sqlite:///", "")
                if db_path.startswith("./"):
                    db_path = os.path.join(os.getcwd(), db_path[2:])
            else:
                db_path = db_url.replace("sqlite:///", "")
            
            # Close database connections first
            self.engine.dispose()
            
            # Backup current database before restore (safety measure)
            current_backup = f"{db_path}.before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            if os.path.exists(db_path):
                shutil.copy2(db_path, current_backup)
                logger.info(f"[DBMigration] Current database backed up to: {current_backup}")
            
            # Restore from backup
            shutil.copy2(backup_path, db_path)
            
            # Note: We do NOT restore WAL/SHM files because:
            # 1. Backup files are standalone snapshots (created with DELETE journal mode)
            # 2. WAL/SHM files are temporary and will be recreated when database is opened
            # 3. Restoring old WAL/SHM files could cause corruption
            
            logger.info(f"[DBMigration] Database restored from: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"[DBMigration] SQLite restore failed: {e}", exc_info=True)
            return False
    
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
        type_str = str(column_def.type)
        
        # SQLite type mapping
        if 'INTEGER' in type_str.upper():
            return 'INTEGER'
        elif 'VARCHAR' in type_str.upper() or 'STRING' in type_str.upper() or 'TEXT' in type_str.upper():
            # Extract length if available
            if hasattr(column_def.type, 'length') and column_def.type.length:
                return f"VARCHAR({column_def.type.length})"
            return 'TEXT'
        elif 'FLOAT' in type_str.upper() or 'REAL' in type_str.upper():
            return 'REAL'
        elif 'BOOLEAN' in type_str.upper():
            return 'BOOLEAN'
        elif 'DATETIME' in type_str.upper() or 'TIMESTAMP' in type_str.upper():
            return 'DATETIME'
        else:
            return type_str
    
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

