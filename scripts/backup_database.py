"""
Database Backup Script for MindGraph
Author: MindSpring Team

Creates timestamped backups of the database using SQLite's backup API.
Safely handles WAL mode databases by automatically checkpointing.

IMPORTANT: You can run backups WHILE the application is running!
The SQLite backup API safely handles active databases in WAL mode.

Usage:
    # Standard usage (reads from config automatically)
    python scripts/backup_database.py
    
    # Standalone mode (when config is not available, e.g., on old server)
    python scripts/backup_database.py --source /data/mindgraph.db
    
    # Custom backup directory (optional)
    python scripts/backup_database.py --backup-dir /backup
    
    # Custom backup filename (optional)
    python scripts/backup_database.py --backup /backup/custom_backup.db
    
    # Verify existing backup integrity
    python scripts/backup_database.py --verify /backup/mindgraph.db.20251211_011839
"""

import shutil
import os
import sys
import sqlite3
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import config (only if needed)
_script_dir = Path(__file__).parent
_project_root = _script_dir.parent
sys.path.insert(0, str(_project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Default configuration - backup directory relative to project root
DEFAULT_BACKUP_DIR = _project_root / "backup"
DEFAULT_DB_PATH = Path("/data/mindgraph.db")

def get_database_path():
    """
    Get the actual database file path from DATABASE_URL configuration.
    Respects DATABASE_URL environment variable or uses default.
    
    SQLite URL formats:
    - sqlite:///./path/to/db (relative path)
    - sqlite:////absolute/path/to/db (absolute path - note 4 slashes)
    - sqlite:///path/to/db (relative path - 3 slashes)
    
    Returns:
        Path object to database file
    """
    try:
        # Try to import from config (requires full codebase)
        from config.database import engine
        
        db_url = str(engine.url)
        
        # Extract file path from SQLite URL
        if db_url.startswith("sqlite:////"):
            # Absolute path (4 slashes: sqlite:////absolute/path)
            db_path = db_url.replace("sqlite:////", "/")
        elif db_url.startswith("sqlite:///"):
            # Relative path (3 slashes: sqlite:///./path or sqlite:///path)
            db_path = db_url.replace("sqlite:///", "")
            if db_path.startswith("./"):
                db_path = db_path[2:]  # Remove "./"
            # Resolve relative to project root, not current working directory
            if not os.path.isabs(db_path):
                db_path = str(_project_root / db_path)
        else:
            # Fallback: try to extract path
            db_path = db_url.replace("sqlite:///", "")
        
        return Path(db_path).resolve()
    except (ImportError, Exception) as e:
        # Fallback to default absolute path
        logger.debug(f"Could not load database config: {e}")
        return DEFAULT_DB_PATH


def backup_using_dump(source_db: Path, backup_db: Path) -> bool:
    """
    Fallback backup method using dump/restore.
    This method is slower but works on all Python versions.
    
    Args:
        source_db: Path to source database file
        backup_db: Path to backup database file
        
    Returns:
        True if backup succeeded, False otherwise
    """
    source_conn = None
    backup_conn = None
    
    try:
        logger.info("Using dump/restore method for backup...")
        source_conn = sqlite3.connect(str(source_db), timeout=60.0)
        
        # Remove existing backup file
        if backup_db.exists():
            backup_db.unlink()
        
        # Create backup database
        backup_conn = sqlite3.connect(str(backup_db), timeout=60.0)
        
        # Dump source database and restore to backup
        for line in source_conn.iterdump():
            backup_conn.executescript(line)
        
        backup_conn.commit()
        
        # Verify backup
        if backup_db.exists() and backup_db.stat().st_size > 0:
            logger.info("Dump/restore backup completed successfully")
            return True
        else:
            logger.error("Dump/restore backup failed - file is empty")
            return False
            
    except Exception as e:
        logger.error(f"Dump/restore backup failed: {e}")
        return False
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


def backup_database_safely(source_db: Path, backup_db: Path) -> bool:
    """
    Safely backup SQLite database using SQLite's backup API.
    This method properly handles WAL mode by automatically checkpointing
    and copying all committed data.
    
    Safe to run while application is running - SQLite backup API handles
    concurrent access correctly.
    
    Args:
        source_db: Path to source database file
        backup_db: Path to backup database file
        
    Returns:
        True if backup succeeded, False otherwise
    """
    source_conn = None
    backup_conn = None
    
    # Verify source database exists and is readable
    if not source_db.exists():
        logger.error(f"Source database does not exist: {source_db}")
        return False
    
    if not os.access(source_db, os.R_OK):
        logger.error(f"Source database is not readable: {source_db}")
        return False
    
    try:
        # Connect to source database with longer timeout for active databases
        # timeout=60.0 allows up to 60 seconds to acquire lock
        logger.debug(f"Connecting to source database: {source_db}")
        source_conn = sqlite3.connect(str(source_db), timeout=60.0)
        
        # Verify source database is accessible
        try:
            source_conn.execute("SELECT 1").fetchone()
        except sqlite3.Error as e:
            logger.error(f"Cannot access source database: {e}")
            return False
        
        # Ensure backup directory exists
        backup_db.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        
        # Remove existing backup file if it exists (atomic operation)
        if backup_db.exists():
            try:
                backup_db.unlink()
            except OSError as e:
                logger.error(f"Cannot remove existing backup file: {e}")
                return False
        
        # Connect to backup database
        logger.debug(f"Creating backup database: {backup_db}")
        backup_conn = sqlite3.connect(str(backup_db), timeout=60.0)
        
        # Use SQLite backup API - this handles WAL mode correctly
        # 
        # HOW IT HANDLES WAL/SHM FILES:
        # ===============================
        # 1. The backup API automatically reads from both:
        #    - The main database file (.db)
        #    - The WAL file (-wal) containing uncommitted transactions
        # 
        # 2. It internally checkpoints the WAL (merges committed transactions)
        #    and includes ALL committed data in the backup
        #
        # 3. The SHM file (-shm) is NOT needed - it's temporary shared memory
        #    that SQLite uses internally and is automatically recreated
        #
        # 4. The result is a SINGLE standalone backup file (.db) that contains
        #    all committed data - NO .wal or .shm files needed!
        #
        # 5. This is safe to run while the application is running because:
        #    - It only READS from source (never modifies)
        #    - It creates a consistent snapshot of committed data
        #    - Ongoing transactions continue normally
        #
        # The backup() method copies FROM source TO backup
        logger.debug("Starting SQLite backup operation...")
        logger.debug("Note: WAL file will be automatically checkpointed and included in backup")
        
        # The backup() method copies FROM source TO backup
        # Check if backup() method is available (Python 3.7+)
        if not hasattr(source_conn, 'backup'):
            logger.error("SQLite backup() method not available")
            logger.error("Python 3.7+ is required for backup() method")
            logger.info("Falling back to dump/restore method...")
            return backup_using_dump(source_db, backup_db)
        
        # Create backup object
        # Check SQLite version and Python version for diagnostics
        try:
            sqlite_version = sqlite3.sqlite_version
            python_version = sys.version_info
            logger.debug(f"SQLite version: {sqlite_version}, Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
            
            # Check if backup method exists
            if not hasattr(source_conn, 'backup'):
                logger.error("backup() method not available on connection object")
                logger.error("This Python/sqlite3 build may not support backup API")
                logger.info("Falling back to dump/restore method...")
                return backup_using_dump(source_db, backup_db)
        except Exception as e:
            logger.debug(f"Version check failed: {e}")
        
        # Create backup object
        # ROOT CAUSE INVESTIGATION:
        # The backup() method signature in Python 3.7+ is:
        #   backup(target, *, pages=-1, progress=None, name="main", sleep=0.250)
        # It should ALWAYS return a Backup object, never None.
        # If it returns None, possible causes:
        #   1. SQLite library compiled without backup support
        #   2. Connection issue (source or target)
        #   3. Python sqlite3 module bug/version issue
        try:
            # Try calling backup() method
            backup = source_conn.backup(backup_conn)
            
            # Check if backup object is None (should never happen)
            if backup is None:
                logger.error("ROOT CAUSE: backup() returned None")
                logger.error("This indicates:")
                logger.error("  1. SQLite library may not support backup API")
                logger.error("  2. Possible Python sqlite3 module issue")
                logger.error("  3. Check SQLite version (need >= 3.6.11)")
                logger.info("Falling back to dump/restore method (also handles WAL correctly)...")
                return backup_using_dump(source_db, backup_db)
            
            # Verify backup object has required methods
            if not hasattr(backup, 'step'):
                logger.error("ROOT CAUSE: backup object missing step() method")
                logger.error("Backup object type: " + str(type(backup)))
                logger.info("Falling back to dump/restore method...")
                return backup_using_dump(source_db, backup_db)
                
        except AttributeError as e:
            logger.warning(f"backup() method not available: {e}")
            logger.info("Falling back to dump/restore method...")
            return backup_using_dump(source_db, backup_db)
        except Exception as e:
            logger.warning(f"backup() method failed: {e}, trying dump/restore method...")
            return backup_using_dump(source_db, backup_db)
        
        # Copy all pages with progress reporting for large databases
        try:
            pages_copied = 0
            while True:
                remaining = backup.step(100)  # Copy 100 pages at a time
                pages_copied += 100
                if remaining == 0:
                    break
                # Log progress for large databases (every 1000 pages)
                if pages_copied % 1000 == 0:
                    logger.debug(f"Backup progress: {pages_copied} pages copied...")
            
            backup.finish()
            logger.debug("Backup operation completed")
        except AttributeError as e:
            logger.warning(f"Backup step() failed: {e}, trying alternative method...")
            # Try alternative: use step(-1) to copy all at once
            try:
                backup.step(-1)  # Copy all pages at once
                backup.finish()
                logger.debug("Backup completed using step(-1)")
            except Exception as e2:
                logger.warning(f"Alternative backup method failed: {e2}, trying dump/restore...")
                return backup_using_dump(source_db, backup_db)
        
        # Verify backup file was created and has content
        if not backup_db.exists():
            logger.error("Backup file was not created")
            return False
        
        backup_size = backup_db.stat().st_size
        if backup_size == 0:
            logger.error("Backup file is empty")
            return False
        
        logger.debug(f"Backup file created: {backup_size} bytes")
        return True
        
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e).lower():
            logger.error(f"Database is locked. Is another backup running? Error: {e}")
            logger.error("Wait a few seconds and try again, or check for other processes accessing the database")
        else:
            logger.error(f"SQLite operational error: {e}")
        # Clean up partial backup file
        try:
            if backup_db.exists():
                backup_db.unlink()
        except (OSError, PermissionError) as cleanup_error:
            logger.warning(f"Could not remove partial backup file: {cleanup_error}")
        return False
    except sqlite3.Error as e:
        logger.error(f"SQLite backup error: {e}")
        # Clean up partial backup file
        try:
            if backup_db.exists():
                backup_db.unlink()
        except (OSError, PermissionError) as cleanup_error:
            logger.warning(f"Could not remove partial backup file: {cleanup_error}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during backup: {e}", exc_info=True)
        # Clean up partial backup file
        try:
            if backup_db.exists():
                backup_db.unlink()
        except (OSError, PermissionError) as cleanup_error:
            logger.warning(f"Could not remove partial backup file: {cleanup_error}")
        return False
    finally:
        # Ensure connections are always closed
        if backup_conn:
            try:
                backup_conn.close()
            except Exception as e:
                logger.debug(f"Error closing backup connection: {e}")
        if source_conn:
            try:
                source_conn.close()
            except Exception as e:
                logger.debug(f"Error closing source connection: {e}")

def verify_backup(backup_path: Path) -> bool:
    """
    Verify backup database integrity.
    
    Args:
        backup_path: Path to backup database file
        
    Returns:
        True if backup is valid, False otherwise
    """
    if not backup_path.exists():
        logger.error(f"Backup file not found: {backup_path}")
        return False
    
    if not backup_path.is_file():
        logger.error(f"Backup path is not a file: {backup_path}")
        return False
    
    if backup_path.stat().st_size == 0:
        logger.error(f"Backup file is empty: {backup_path}")
        return False
    
    conn = None
    try:
        conn = sqlite3.connect(str(backup_path), timeout=30.0)
        cursor = conn.cursor()
        
        # Run integrity check
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        
        # Also check quick integrity check
        cursor.execute("PRAGMA quick_check")
        quick_result = cursor.fetchone()
        
        conn.close()
        
        if result and result[0] == "ok" and quick_result and quick_result[0] == "ok":
            logger.info(f"Backup integrity check passed: {backup_path}")
            return True
        else:
            logger.error(f"Backup integrity check failed")
            if result:
                logger.error(f"  Full check: {result[0]}")
            if quick_result:
                logger.error(f"  Quick check: {quick_result[0]}")
            return False
    except sqlite3.Error as e:
        logger.error(f"Error checking backup integrity: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def create_backup(source_db: Path = None, backup_path: Path = None, backup_dir: Path = None, keep_backups: int = 10):
    """
    Create timestamped backup of database.
    
    Args:
        source_db: Path to source database (None = auto-detect from config)
        backup_path: Full path to backup file (None = auto-generate with timestamp)
        backup_dir: Directory for backups (None = use default)
        keep_backups: Number of backups to keep (default: 10)
    """
    # Determine source database path
    if source_db is None:
        source_db = get_database_path()
    else:
        source_db = Path(source_db).resolve()
    
    # Check if source database exists
    if not source_db.exists():
        logger.error(f"Database not found: {source_db}")
        logger.error("Please specify the correct database path using --source")
        return False
    
    # Determine backup directory
    if backup_dir is None:
        backup_dir = DEFAULT_BACKUP_DIR
    else:
        backup_dir = Path(backup_dir)
        # If relative path, make it relative to project root
        if not backup_dir.is_absolute():
            backup_dir = _project_root / backup_dir
    
    # Resolve to absolute path
    backup_dir = backup_dir.resolve()
    
    # Check disk space (rough estimate: need at least 2x database size)
    try:
        if source_db.exists():
            db_size = source_db.stat().st_size
            required_space = db_size * 2  # Need at least 2x for safety
            
            # Check available space (Unix/Linux)
            try:
                stat = os.statvfs(backup_dir.parent)
                free_space = stat.f_bavail * stat.f_frsize
                if free_space < required_space:
                    logger.warning(f"Low disk space: {free_space / (1024*1024):.1f} MB free, "
                                f"need at least {required_space / (1024*1024):.1f} MB")
                    logger.warning("Backup may fail if disk space runs out")
            except AttributeError:
                # Windows doesn't have statvfs, skip check
                pass
    except Exception as e:
        logger.debug(f"Could not check disk space: {e}")
    
    # Create backup directory if it doesn't exist
    try:
        backup_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
    except OSError as e:
        logger.error(f"Failed to create backup directory {backup_dir}: {e}")
        logger.error(f"Please ensure you have write permissions to {backup_dir.parent}")
        return False
    
    # Verify we can write to backup directory
    try:
        test_file = backup_dir / ".backup_test"
        test_file.write_text("test")
        test_file.unlink()
    except Exception as e:
        logger.error(f"Cannot write to backup directory {backup_dir}: {e}")
        return False
    
    # Determine backup file path
    if backup_path is None:
        # Generate timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"mindgraph.db.{timestamp}"
        backup_db_path = backup_dir / backup_filename
    else:
        backup_db_path = Path(backup_path).resolve()
        # Ensure backup directory exists
        backup_db_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Creating backup: {backup_db_path}")
    logger.info(f"Database location: {source_db}")
    
    # Backup database using safe WAL-aware method
    logger.info("Creating safe backup (handles WAL mode)...")
    if backup_database_safely(source_db, backup_db_path):
        # Verify backup was created successfully
        if backup_db_path.exists() and backup_db_path.stat().st_size > 0:
            size_mb = backup_db_path.stat().st_size / (1024 * 1024)
            logger.info(f"Database backed up safely: {backup_db_path.name} ({size_mb:.2f} MB)")
            logger.info("Backup includes all committed data from WAL mode")
            
            # Verify integrity
            if verify_backup(backup_db_path):
                logger.info("Backup integrity verified")
            else:
                logger.warning("Backup created but integrity check failed")
            
            # Clean up old backups if using auto-generated filename
            if backup_path is None:
                cleanup_old_backups(backup_dir, keep_backups)
            
            logger.info("Backup completed successfully")
            logger.info(f"Location: {backup_db_path}")
            return True
        else:
            logger.error("Backup file was not created or is empty")
            return False
    else:
        logger.warning("Safe backup failed, falling back to file copy...")
        # Fallback to simple copy (less safe but better than nothing)
        try:
            # Remove any partial backup file first
            if backup_db_path.exists():
                backup_db_path.unlink()
            shutil.copy2(source_db, backup_db_path)
            if backup_db_path.exists() and backup_db_path.stat().st_size > 0:
                size_mb = backup_db_path.stat().st_size / (1024 * 1024)
                logger.info(f"Database copied: {backup_db_path.name} ({size_mb:.2f} MB)")
                logger.warning("File copy may miss uncommitted WAL changes")
                logger.warning("This backup method is not recommended for WAL mode databases")
                return True
            else:
                logger.error("File copy failed - backup file is empty")
                return False
        except (OSError, shutil.Error) as e:
            logger.error(f"File copy failed: {e}")
            return False

def cleanup_old_backups(backup_dir: Path = None, keep: int = 10):
    """
    Remove old backups, keeping only the most recent ones.
    
    Args:
        backup_dir: Directory containing backups (None = use default)
        keep: Number of backups to keep
    """
    if backup_dir is None:
        backup_dir = DEFAULT_BACKUP_DIR
    
    if not backup_dir.exists():
        return
    
    try:
        # Get all backup files
        backups = list(backup_dir.glob("mindgraph.db.*"))
        
        # Filter to only include files (not directories) and sort by modification time
        backup_files = []
        for backup in backups:
            try:
                if backup.is_file():
                    backup_files.append(backup)
            except (OSError, PermissionError):
                # Skip files we can't access
                continue
        
        # Sort by modification time (newest first)
        backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Remove old backups
        if len(backup_files) > keep:
            for old_backup in backup_files[keep:]:
                try:
                    logger.info(f"Removing old backup: {old_backup.name}")
                    old_backup.unlink()
                except (OSError, PermissionError) as e:
                    logger.warning(f"Could not remove {old_backup.name}: {e}")
    except (OSError, PermissionError) as e:
        logger.warning(f"Could not clean up old backups: {e}")


def main():
    """Main entry point with command-line argument parsing"""
    parser = argparse.ArgumentParser(
        description="Safely backup SQLite database (handles WAL mode)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Standard usage (reads from config)
  python scripts/backup_database.py
  
  # Standalone mode with custom paths
  python scripts/backup_database.py --source /data/mindgraph.db --backup-dir /backup
  
  # Custom backup filename
  python scripts/backup_database.py --source /data/mindgraph.db --backup /backup/my_backup.db
  
  # Verify existing backup
  python scripts/backup_database.py --verify /backup/mindgraph.db.20251211_011839
        """
    )
    
    parser.add_argument(
        "--source",
        type=str,
        help="Path to source database file (default: auto-detect from config)"
    )
    
    parser.add_argument(
        "--backup",
        type=str,
        help="Full path to backup file (default: auto-generate with timestamp)"
    )
    
    parser.add_argument(
        "--backup-dir",
        type=str,
        default=None,
        help=f"Directory for backups (default: {DEFAULT_BACKUP_DIR} - project root/backup)"
    )
    
    parser.add_argument(
        "--keep",
        type=int,
        default=10,
        help="Number of backups to keep (default: 10)"
    )
    
    parser.add_argument(
        "--verify",
        type=str,
        help="Verify integrity of existing backup file"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("MindGraph Database Backup Tool")
    logger.info("=" * 60)
    
    # Handle verify mode
    if args.verify:
        backup_path = Path(args.verify).resolve()
        if verify_backup(backup_path):
            sys.exit(0)
        else:
            sys.exit(1)
    
    # Handle backup mode
    source_db = Path(args.source).resolve() if args.source else None
    backup_path = Path(args.backup).resolve() if args.backup else None
    backup_dir = Path(args.backup_dir) if args.backup_dir else None
    
    # Log configuration
    logger.info(f"Project root: {_project_root}")
    if backup_dir:
        logger.info(f"Backup directory: {backup_dir}")
    else:
        logger.info(f"Backup directory: {DEFAULT_BACKUP_DIR} (default)")
    
    success = create_backup(
        source_db=source_db,
        backup_path=backup_path,
        backup_dir=backup_dir,
        keep_backups=args.keep
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

