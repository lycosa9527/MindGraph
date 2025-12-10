"""
Database Recovery Script for MindGraph
======================================

Recovers corrupted SQLite databases by:
1. Attempting to dump and restore data
2. Rebuilding WAL files if corrupted
3. Creating backups before recovery attempts

Usage:
    python scripts/recover_database.py [--force] [--backup-only]

Author: MindSpring Team
"""

import sqlite3
import shutil
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def get_database_path():
    """
    Get the actual database file path from DATABASE_URL configuration.
    """
    try:
        from config.database import engine
        db_url = str(engine.url)
        
        # Extract file path from SQLite URL
        if db_url.startswith("sqlite:////"):
            db_path = db_url.replace("sqlite:////", "/")
        elif db_url.startswith("sqlite:///"):
            db_path = db_url.replace("sqlite:///", "")
            if db_path.startswith("./"):
                db_path = db_path[2:]
            if not os.path.isabs(db_path):
                # Resolve relative to project root (parent of scripts directory)
                project_root = Path(__file__).parent.parent
                db_path = os.path.join(project_root, db_path)
        else:
            db_path = db_url.replace("sqlite:///", "")
        
        return Path(db_path).resolve()
    except Exception as e:
        logger.error(f"Failed to determine database path: {e}")
        # Fallback to default absolute path /data/mindgraph.db
        return Path("/data/mindgraph.db")


def check_disk_space(db_path: Path, required_mb: int = 100):
    """Check if there's enough disk space for recovery"""
    try:
        stat = os.statvfs(db_path.parent)
        free_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)
        if free_mb < required_mb:
            logger.error(f"Insufficient disk space: {free_mb:.1f} MB available, {required_mb} MB required")
            return False
        return True
    except AttributeError:
        # Windows doesn't have statvfs, skip check
        return True


def backup_database(db_path: Path) -> Path:
    """Create backup of database before recovery"""
    # Create backups directory relative to project root
    project_root = Path(__file__).parent.parent
    backup_dir = project_root / "backups"
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{db_path.name}.corrupted_{timestamp}"
    
    logger.info(f"Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    
    # Also backup WAL/SHM files if they exist
    for suffix in ["-wal", "-shm"]:
        wal_shm_file = Path(str(db_path) + suffix)
        if wal_shm_file.exists():
            backup_wal = backup_dir / f"{db_path.name}{suffix}.corrupted_{timestamp}"
            shutil.copy2(wal_shm_file, backup_wal)
            logger.info(f"Backed up {wal_shm_file.name}")
    
    return backup_path


def check_integrity(db_path: Path) -> bool:
    """Check database integrity"""
    logger.info("Checking database integrity...")
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] == "ok":
            logger.info("Database integrity check passed")
            return True
        else:
            logger.error(f"Database integrity check failed: {result}")
            return False
    except sqlite3.DatabaseError as e:
        logger.error(f"Database integrity check error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during integrity check: {e}")
        return False


def recover_database(db_path: Path, force: bool = False) -> bool:
    """
    Recover corrupted database by dumping and restoring.
    
    Returns:
        True if recovery succeeded, False otherwise
    """
    logger.info(f"Starting database recovery for: {db_path}")
    
    if not db_path.exists():
        logger.error(f"Database file not found: {db_path}")
        return False
    
    # Check disk space
    if not check_disk_space(db_path, required_mb=200):
        logger.error("Insufficient disk space for recovery")
        return False
    
    # Create backup before recovery
    backup_path = backup_database(db_path)
    logger.info(f"Backup created: {backup_path}")
    
    # Step 1: Try to checkpoint WAL file (may fix some corruption)
    logger.info("Attempting WAL checkpoint...")
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        # Try to checkpoint and truncate WAL
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        result = cursor.fetchone()
        conn.close()
        logger.info(f"WAL checkpoint result: {result}")
    except Exception as e:
        logger.warning(f"WAL checkpoint failed (may be expected): {e}")
    
    # Step 2: Try integrity check
    if check_integrity(db_path):
        logger.info("Database is healthy after WAL checkpoint")
        return True
    
    # Step 3: Attempt dump and restore
    logger.info("Attempting dump and restore recovery...")
    
    # Create temporary dump file
    dump_file = db_path.parent / f"{db_path.name}.dump_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    recovered_db = db_path.parent / f"{db_path.name}.recovered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    dump_file_created = False
    
    try:
        # Dump database to SQL file
        logger.info("Dumping database to SQL file...")
        conn = sqlite3.connect(str(db_path))
        with open(dump_file, 'w', encoding='utf-8') as f:
            for line in conn.iterdump():
                f.write(f"{line}\n")
        conn.close()
        dump_file_created = True
        
        # Create new database from dump
        logger.info("Creating new database from dump...")
        if recovered_db.exists():
            recovered_db.unlink()
        
        conn = sqlite3.connect(str(recovered_db))
        with open(dump_file, 'r', encoding='utf-8') as f:
            conn.executescript(f.read())
        conn.close()
        
        # Verify recovered database
        if check_integrity(recovered_db):
            logger.info("Recovered database integrity check passed")
            
            # Replace original with recovered database
            if force:
                # Remove WAL/SHM files
                for suffix in ["-wal", "-shm"]:
                    wal_shm_file = Path(str(db_path) + suffix)
                    if wal_shm_file.exists():
                        wal_shm_file.unlink()
                        logger.info(f"Removed {wal_shm_file.name}")
                
                # Replace database
                db_path.unlink()
                shutil.move(str(recovered_db), str(db_path))
                logger.info(f"Database recovered successfully: {db_path}")
                
                # Cleanup dump file
                dump_file.unlink()
                return True
            else:
                logger.info(f"Recovered database created: {recovered_db}")
                logger.info("Use --force to replace original database")
                return False
        else:
            logger.error("Recovered database failed integrity check")
            return False
            
    except sqlite3.DatabaseError as e:
        logger.error(f"Standard dump recovery failed: {e}")
        logger.info("Attempting advanced recovery methods...")
        
        # Try advanced recovery methods
        recovered_db = db_path.parent / f"{db_path.name}.recovered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        # Method 1: Try SQLite .recover command
        if recover_using_sqlite_recover(db_path, recovered_db):
            if force:
                # Remove WAL/SHM files
                for suffix in ["-wal", "-shm"]:
                    wal_shm_file = Path(str(db_path) + suffix)
                    if wal_shm_file.exists():
                        wal_shm_file.unlink()
                        logger.info(f"Removed {wal_shm_file.name}")
                
                # Replace database
                db_path.unlink()
                shutil.move(str(recovered_db), str(db_path))
                logger.info(f"Database recovered successfully using advanced method: {db_path}")
                return True
            else:
                logger.info(f"Recovered database created: {recovered_db}")
                logger.info("Use --force to replace original database")
                return False
        
        # Method 2: Try table-by-table recovery
        logger.info("Trying table-by-table recovery as last resort...")
        recovered_db_table = db_path.parent / f"{db_path.name}.recovered_table_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        if recover_using_table_scan(db_path, recovered_db_table):
            if force:
                # Remove WAL/SHM files
                for suffix in ["-wal", "-shm"]:
                    wal_shm_file = Path(str(db_path) + suffix)
                    if wal_shm_file.exists():
                        wal_shm_file.unlink()
                        logger.info(f"Removed {wal_shm_file.name}")
                
                # Replace database
                db_path.unlink()
                shutil.move(str(recovered_db_table), str(db_path))
                logger.info(f"Database partially recovered using table scan: {db_path}")
                logger.warning("Some data may be missing - please verify recovered data")
                return True
            else:
                logger.info(f"Partially recovered database created: {recovered_db_table}")
                logger.info("Use --force to replace original database")
                logger.warning("Some data may be missing - please verify recovered data")
                return False
        
        logger.error("All recovery methods failed. Database may be severely corrupted.")
        logger.error("Manual recovery may be required.")
        return False
        
    except Exception as e:
        logger.error(f"Unexpected error during recovery: {e}", exc_info=True)
        return False
    finally:
        # Cleanup temporary files
        if dump_file_created and dump_file.exists():
            if not force:
                logger.info(f"Dump file saved: {dump_file}")
            else:
                dump_file.unlink()


def recover_using_sqlite_recover(db_path: Path, recovered_db: Path) -> bool:
    """
    Attempt recovery using SQLite's .recover command (SQLite 3.29+).
    This can recover data from severely corrupted databases.
    
    Returns:
        True if recovery succeeded, False otherwise
    """
    logger.info("Attempting advanced recovery using SQLite .recover command...")
    
    try:
        # Check if sqlite3 command-line tool is available
        result = subprocess.run(
            ["sqlite3", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            logger.warning("sqlite3 command-line tool not available, skipping .recover method")
            return False
        
        # Get SQLite version
        version_output = result.stdout.strip()
        logger.info(f"SQLite version: {version_output}")
        
        # Use .recover to dump recoverable data
        dump_file = db_path.parent / f"{db_path.name}.recover_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        
        logger.info(f"Running sqlite3 .recover command...")
        with open(dump_file, 'w', encoding='utf-8') as f:
            result = subprocess.run(
                ["sqlite3", str(db_path), ".recover"],
                stdout=f,
                stderr=subprocess.PIPE,
                timeout=300,  # 5 minute timeout
                text=True
            )
        
        if result.returncode != 0:
            logger.warning(f"sqlite3 .recover command failed: {result.stderr}")
            if dump_file.exists() and dump_file.stat().st_size == 0:
                dump_file.unlink()
            return False
        
        if not dump_file.exists() or dump_file.stat().st_size == 0:
            logger.warning("Recovery dump file is empty")
            if dump_file.exists():
                dump_file.unlink()
            return False
        
        logger.info(f"Recovery dump created: {dump_file} ({dump_file.stat().st_size} bytes)")
        
        # Create new database from recovery dump
        logger.info("Creating new database from recovery dump...")
        if recovered_db.exists():
            recovered_db.unlink()
        
        conn = sqlite3.connect(str(recovered_db))
        try:
            with open(dump_file, 'r', encoding='utf-8') as f:
                # Read and execute SQL statements
                sql_script = f.read()
                # Split by semicolons and execute each statement
                for statement in sql_script.split(';'):
                    statement = statement.strip()
                    if statement:
                        try:
                            conn.execute(statement)
                        except sqlite3.Error as e:
                            # Some statements might fail, but continue with others
                            logger.debug(f"Skipping failed statement: {e}")
                conn.commit()
        finally:
            conn.close()
        
        # Verify recovered database
        if recovered_db.exists() and recovered_db.stat().st_size > 0:
            if check_integrity(recovered_db):
                logger.info("Advanced recovery succeeded - database integrity check passed")
                dump_file.unlink()  # Clean up dump file
                return True
            else:
                logger.warning("Recovered database created but integrity check failed")
                logger.info(f"Recovery dump saved at: {dump_file}")
                logger.info("You may need to manually review and fix the recovered data")
                return False
        else:
            logger.error("Recovered database file was not created or is empty")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("Recovery operation timed out (database may be too large)")
        return False
    except FileNotFoundError:
        logger.warning("sqlite3 command-line tool not found, skipping .recover method")
        return False
    except Exception as e:
        logger.error(f"Advanced recovery failed: {e}", exc_info=True)
        return False


def recover_using_table_scan(db_path: Path, recovered_db: Path) -> bool:
    """
    Attempt to recover data by scanning individual tables.
    This method tries to read data from tables that might still be accessible.
    
    Returns:
        True if any data was recovered, False otherwise
    """
    logger.info("Attempting table-by-table recovery...")
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Try to get list of tables
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            logger.info(f"Found {len(tables)} tables to attempt recovery")
        except Exception as e:
            logger.error(f"Could not read table list: {e}")
            conn.close()
            return False
        
        if not tables:
            logger.warning("No tables found in database")
            conn.close()
            return False
        
        # Create recovered database
        if recovered_db.exists():
            recovered_db.unlink()
        recovered_conn = sqlite3.connect(str(recovered_db))
        recovered_cursor = recovered_conn.cursor()
        
        recovered_tables = 0
        total_rows = 0
        
        for table in tables:
            try:
                # Try to get table schema
                cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
                schema_row = cursor.fetchone()
                if schema_row and schema_row[0]:
                    schema = schema_row[0]
                    # Create table in recovered database
                    recovered_cursor.execute(schema)
                    logger.info(f"Created table: {table}")
                    
                    # Try to read data from table
                    try:
                        cursor.execute(f"SELECT * FROM {table}")
                        rows = cursor.fetchall()
                        
                        if rows:
                            # Get column names
                            column_names = [description[0] for description in cursor.description]
                            placeholders = ','.join(['?' for _ in column_names])
                            insert_sql = f"INSERT INTO {table} ({','.join(column_names)}) VALUES ({placeholders})"
                            
                            # Insert rows into recovered database
                            recovered_cursor.executemany(insert_sql, rows)
                            recovered_tables += 1
                            total_rows += len(rows)
                            logger.info(f"Recovered {len(rows)} rows from table: {table}")
                    except Exception as e:
                        logger.warning(f"Could not recover data from table {table}: {e}")
                        # Table structure recovered but no data
                        recovered_tables += 1
                        
            except Exception as e:
                logger.warning(f"Could not recover table {table}: {e}")
                continue
        
        recovered_conn.commit()
        recovered_conn.close()
        conn.close()
        
        if recovered_tables > 0:
            logger.info(f"Table recovery: {recovered_tables} tables recovered, {total_rows} total rows")
            if check_integrity(recovered_db):
                logger.info("Table recovery succeeded - database integrity check passed")
                return True
            else:
                logger.warning("Table recovery created database but integrity check failed")
                logger.info("Partial recovery may be possible - review recovered data")
                return False
        else:
            logger.error("No tables could be recovered")
            return False
            
    except Exception as e:
        logger.error(f"Table recovery failed: {e}", exc_info=True)
        return False


def remove_wal_files(db_path: Path) -> bool:
    """Remove WAL and SHM files (use with caution)"""
    logger.warning("Removing WAL/SHM files...")
    removed = False
    for suffix in ["-wal", "-shm"]:
        wal_shm_file = Path(str(db_path) + suffix)
        if wal_shm_file.exists():
            wal_shm_file.unlink()
            logger.info(f"Removed {wal_shm_file.name}")
            removed = True
    return removed


def main():
    parser = argparse.ArgumentParser(description="Recover corrupted SQLite database")
    parser.add_argument("--force", action="store_true", help="Force recovery (replace original database)")
    parser.add_argument("--backup-only", action="store_true", help="Only create backup, don't recover")
    parser.add_argument("--remove-wal", action="store_true", help="Remove WAL/SHM files (dangerous)")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("MindGraph Database Recovery Tool")
    print("=" * 80)
    print()
    
    try:
        db_path = get_database_path()
        logger.info(f"Database path: {db_path}")
        
        if not db_path.exists():
            logger.error(f"Database file not found: {db_path}")
            sys.exit(1)
        
        if args.backup_only:
            backup_path = backup_database(db_path)
            logger.info(f"Backup created: {backup_path}")
            sys.exit(0)
        
        if args.remove_wal:
            if remove_wal_files(db_path):
                logger.info("WAL files removed. Restart server to recreate them.")
            else:
                logger.info("No WAL files found to remove.")
            sys.exit(0)
        
        # Check integrity first
        if check_integrity(db_path):
            logger.info("Database is healthy - no recovery needed")
            sys.exit(0)
        
        # Attempt recovery
        if recover_database(db_path, force=args.force):
            logger.info("=" * 80)
            logger.info("RECOVERY SUCCESSFUL")
            logger.info("=" * 80)
            logger.info("Please restart your server to verify the database is working correctly.")
            sys.exit(0)
        else:
            logger.error("=" * 80)
            logger.error("RECOVERY FAILED")
            logger.error("=" * 80)
            logger.error("The database may be severely corrupted.")
            logger.error("Options:")
            logger.error("1. Restore from a recent backup")
            logger.error("2. Contact support with the backup file")
            logger.error("3. If data loss is acceptable, delete the database and restart")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\nRecovery interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

