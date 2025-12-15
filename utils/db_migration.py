"""
Database Migration Manager
==========================

Automatically validates and patches database schema on startup.
Detects missing columns and adds them automatically.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from sqlalchemy import inspect, text, MetaData, Table
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from config.database import engine, SessionLocal

logger = logging.getLogger(__name__)


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
        # Verify we're using SQLite (only supported database)
        db_url = str(self.engine.url)
        if 'sqlite' not in db_url.lower():
            logger.warning(
                f"[DBMigration] Database appears to be non-SQLite: {db_url}. "
                f"Migration manager is optimized for SQLite only. "
                f"Unexpected behavior may occur."
            )
        
    def validate_and_migrate(self) -> bool:
        """
        Validate database schema and apply migrations.
        
        Returns:
            True if migration successful, False otherwise
        """
        try:
            logger.info("[DBMigration] Starting database schema validation...")
            
            # Step 1: Detect missing columns (will trigger backup and migration)
            changes_detected = self._detect_changes()
            
            # Step 2: Create backup if missing columns detected
            backup_path = None
            if changes_detected:
                backup_path = self._create_backup()
                if not backup_path:
                    logger.error("[DBMigration] Backup creation failed - aborting migration for safety")
                    return False
            
            # Step 3: Check and migrate all registered models
            migrations_applied = 0
            
            # Import all models to register them with Base
            from models.auth import Organization, User, APIKey, Base
            
            # Try to import TokenUsage if it exists
            try:
                from models.token_usage import TokenUsage
                logger.debug("[DBMigration] TokenUsage model found")
            except ImportError:
                logger.debug("[DBMigration] TokenUsage model not found (okay if not implemented yet)")
                TokenUsage = None
            
            # Migrate each table
            for table_name, table_class in self._get_registered_tables():
                if table_name and table_class:
                    migrated = self._migrate_table(table_name, table_class)
                    if migrated:
                        migrations_applied += 1
            
            if migrations_applied > 0:
                logger.info(f"[DBMigration] Applied {migrations_applied} table migration(s)")
                if backup_path:
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
            # Import all models to register them with Base
            from models.auth import Organization, User, APIKey, Base
            
            try:
                from models.token_usage import TokenUsage
            except ImportError:
                TokenUsage = None
            
            # Check each table for changes
            for table_name, table_class in self._get_registered_tables():
                if not table_name or not self.inspector.has_table(table_name):
                    continue
                
                # Get existing and expected columns
                existing_columns = {
                    col['name']: col 
                    for col in self.inspector.get_columns(table_name)
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
                
                # Check for missing columns (will be added - needs backup)
                for col_name in expected_columns:
                    if col_name not in existing_columns:
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
        """Create backup for SQLite database by copying the file"""
        try:
            db_url = str(self.engine.url)
            # Extract file path from SQLite URL
            # SQLite URL formats:
            # - sqlite:///./path/to/db (relative path)
            # - sqlite:////absolute/path/to/db (absolute path - note 4 slashes)
            # - sqlite:///path/to/db (relative path - 3 slashes)
            if db_url.startswith("sqlite:////"):
                # Absolute path (4 slashes: sqlite:////absolute/path)
                db_path = db_url.replace("sqlite:////", "/")
            elif db_url.startswith("sqlite:///"):
                # Relative path (3 slashes: sqlite:///./path or sqlite:///path)
                db_path = db_url.replace("sqlite:///", "")
                if db_path.startswith("./"):
                    db_path = db_path[2:]  # Remove "./"
                # Convert to absolute path
                if not os.path.isabs(db_path):
                    db_path = os.path.join(os.getcwd(), db_path)
            else:
                # Fallback: try to extract path
                db_path = db_url.replace("sqlite:///", "")
            
            if not os.path.exists(db_path):
                logger.warning(f"[DBMigration] Database file not found: {db_path} - skipping backup")
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
            import sqlite3
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
            # Check if table exists
            if not self.inspector.has_table(table_name):
                logger.info(f"[DBMigration] Table '{table_name}' does not exist")
                logger.info(f"[DBMigration] Table will be created by Base.metadata.create_all() in init_db()")
                # Note: Table creation happens in init_db() via Base.metadata.create_all()
                # Migration manager only handles adding columns to existing tables
                return False
            
            # Get existing columns
            existing_columns = {
                col['name']: col 
                for col in self.inspector.get_columns(table_name)
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
            
            # Find missing columns only (simple: just check what's missing)
            missing_columns = []
            
            for col_name, col_def in expected_columns.items():
                if col_name not in existing_columns:
                    missing_columns.append((col_name, col_def))
            
            # Only migrate if there are missing columns
            if not missing_columns:
                return False
            
            # Apply migrations: backup → add missing columns
            logger.info(f"[DBMigration] Table '{table_name}': Found {len(missing_columns)} missing column(s) to add")
            
            db = SessionLocal()
            try:
                # Add missing columns (SQLite supports ADD COLUMN)
                for col_name, col_def in missing_columns:
                    self._add_column(table_name, col_name, col_def, db)
                    logger.info(f"[DBMigration] ✅ Added column '{col_name}' to table '{table_name}'")
                
                db.commit()
                
                # Verify columns were actually added (safety check)
                # Recreate inspector to see new columns
                from sqlalchemy import inspect
                fresh_inspector = inspect(self.engine)
                updated_columns = {
                    col['name']: col 
                    for col in fresh_inspector.get_columns(table_name)
                }
                
                # Verify added columns exist
                all_added = True
                for col_name, _ in missing_columns:
                    if col_name not in updated_columns:
                        logger.error(f"[DBMigration] WARNING: Column '{col_name}' was not added to '{table_name}' - verification failed!")
                        all_added = False
                
                if all_added:
                    logger.info(f"[DBMigration] Table '{table_name}': ✅ All {len(missing_columns)} column(s) added and verified successfully")
                    return True
                else:
                    logger.error(f"[DBMigration] Table '{table_name}': Verification failed - some columns may not have been added")
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
    
    def _add_column(self, table_name: str, column_name: str, column_def: Any, db: Session):
        """
        Add a column to a table.
        
        Args:
            table_name: Table name
            column_name: Column name to add
            column_def: SQLAlchemy Column definition
            db: Database session
        """
        # Build SQLite ALTER TABLE statement
        sql = self._build_sqlite_alter_table(table_name, column_name, column_def)
        
        logger.debug(f"[DBMigration] Executing: {sql}")
        db.execute(text(sql))
    
    def _build_sqlite_alter_table(self, table_name: str, column_name: str, column_def: Any) -> str:
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
            SQL ALTER TABLE statement
        """
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
        
        return f"ALTER TABLE {table_name} ADD COLUMN {column_name} {col_type} {nullable}{default_clause}"
    
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

