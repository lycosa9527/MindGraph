"""
SQLite Migration Backup Functions

Functions for backing up and moving SQLite database files during migration.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import sqlite3
import logging
import shutil
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Any

logger = logging.getLogger(__name__)

# Calculate project root
# File structure: MindGraph/utils/migration/sqlite/migration_backup.py
# So: __file__.parent.parent.parent.parent = MindGraph/ (project root)
_project_root = Path(__file__).parent.parent.parent.parent

# Migration configuration constants
BACKUP_DIR = _project_root / "backup"  # Backup folder at project root: MindGraph/backup/
MOVE_RETRY_MAX_ATTEMPTS = 3  # Maximum retry attempts for moving SQLite database
MOVE_RETRY_INITIAL_DELAY = 0.5  # Initial delay before retry (seconds)


def backup_sqlite_database(sqlite_path: Path, progress_tracker: Optional[Any] = None) -> Optional[Path]:
    """
    Backup SQLite database to backup folder.

    For proper backup consistency:
    - Checkpoints WAL file to merge uncommitted changes into main database
    - Only backs up the main database file (after checkpointing)
    - Does NOT backup SHM files (they're process-specific temporary files)
    - Does NOT backup WAL files separately (they're merged via checkpoint)

    Args:
        sqlite_path: Path to SQLite database file
        progress_tracker: Optional progress tracker for displaying progress
            (currently unused - stage is updated by caller)

    Returns:
        Path to backup file, or None if backup failed
    """
    # progress_tracker parameter kept for API consistency, but stage is updated by caller
    _ = progress_tracker
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"mindgraph.db.original.{timestamp}.sqlite"
        backup_path = BACKUP_DIR / backup_filename

        logger.info("[Migration] Backing up SQLite database to %s", backup_path)

        # STEP 1: Checkpoint WAL file to merge uncommitted changes into main database
        # This ensures the backup is consistent and self-contained
        wal_path = Path(str(sqlite_path) + "-wal")
        if wal_path.exists():
            logger.info("[Migration] Checkpointing WAL file to ensure consistent backup...")
            try:
                # Connect to SQLite and checkpoint WAL
                checkpoint_conn = sqlite3.connect(str(sqlite_path))
                checkpoint_cursor = checkpoint_conn.cursor()
                # PRAGMA wal_checkpoint(TRUNCATE) merges WAL into main DB and truncates WAL
                checkpoint_cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                checkpoint_result = checkpoint_cursor.fetchone()
                if checkpoint_result:
                    busy, _, checkpointed_pages = (
                        checkpoint_result[0],
                        checkpoint_result[1],
                        checkpoint_result[2]
                    )
                    if busy == 0:
                        logger.debug(
                            "[Migration] WAL checkpoint completed: %d pages checkpointed",
                            checkpointed_pages
                        )
                    else:
                        logger.warning(
                            "[Migration] WAL checkpoint busy: %d pages checkpointed (some readers/writers active)",
                            checkpointed_pages
                        )
                checkpoint_cursor.close()
                checkpoint_conn.close()
                logger.info("[Migration] WAL checkpoint completed - backup will be consistent")
            except Exception as checkpoint_error:
                logger.warning(
                    "[Migration] WAL checkpoint failed (proceeding anyway): %s",
                    checkpoint_error
                )
                # Continue with backup even if checkpoint fails - might be read-only or locked

        # STEP 2: Copy main database file (now contains all committed data after checkpoint)
        # Use copyfile (not copy2) - WSL/Windows mounts fail on copystat/copymode
        shutil.copyfile(sqlite_path, backup_path)
        logger.debug("[Migration] Backed up main database file")

        # STEP 3: Also create a copy with .original.sqlite suffix for easy identification
        original_backup = BACKUP_DIR / "mindgraph.db.original.sqlite"
        if original_backup.exists():
            original_backup.unlink()
            # Remove any old WAL/SHM files if they exist (shouldn't, but clean up)
            for suffix in ["-wal", "-shm"]:
                old_file = Path(str(original_backup) + suffix)
                if old_file.exists():
                    old_file.unlink()

        shutil.copyfile(sqlite_path, original_backup)
        logger.debug("[Migration] Created .original.sqlite backup")

        # NOTE: We do NOT backup WAL or SHM files because:
        # - WAL: Already checkpointed into main DB, no longer needed
        # - SHM: Process-specific temporary file, will cause issues if restored
        # The backup is self-contained and consistent without these files

        logger.info("[Migration] Backup created: %s (consistent, self-contained)", backup_path)
        return backup_path
    except Exception as e:
        logger.error("[Migration] Failed to backup SQLite database: %s", e)
        return None


def move_sqlite_database_to_backup(sqlite_path: Path, sqlite_conn: Optional[sqlite3.Connection] = None) -> bool:
    """
    Move SQLite database to backup folder after successful migration.

    This is the final step - only called after migration is verified successful.
    The database is moved (not copied) to prevent accidental reuse.

    Includes retry logic with exponential backoff and verification that move succeeded.

    Note: Only moves the main database file. WAL and SHM files are not moved:
    - WAL: Should be empty/truncated after checkpoint (if exists, will be cleaned up)
    - SHM: Process-specific temporary file, will be recreated automatically

    Args:
        sqlite_path: Path to SQLite database file
        sqlite_conn: SQLite connection (will be closed before move)

    Returns:
        True if move succeeded, False otherwise
    """
    # Ensure SQLite connection is closed before attempting move
    if sqlite_conn:
        try:
            sqlite_conn.close()
            logger.debug("[Migration] Closed SQLite connection before move")
        except Exception as e:
            logger.warning("[Migration] Error closing SQLite connection: %s", e)

    # Wait a moment for file handles to release
    time.sleep(MOVE_RETRY_INITIAL_DELAY)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    moved_filename = f"mindgraph.db.migrated.{timestamp}.sqlite"
    moved_path = BACKUP_DIR / moved_filename

    # Retry logic with exponential backoff
    for attempt in range(MOVE_RETRY_MAX_ATTEMPTS):
        try:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)

            logger.info(
                "[Migration] Moving SQLite database to backup (attempt %d/%d): %s",
                attempt + 1, MOVE_RETRY_MAX_ATTEMPTS, moved_path
            )

            # Move main database file
            shutil.move(str(sqlite_path), str(moved_path))

            # Verify move succeeded
            if not moved_path.exists():
                raise RuntimeError("Move reported success but destination file not found")
            if sqlite_path.exists():
                raise RuntimeError("Original file still exists after move")

            logger.debug("[Migration] Moved main database file successfully")

            # Clean up WAL and SHM files if they exist (they're no longer needed)
            # These are temporary files that shouldn't be moved/backed up
            wal_path = Path(str(sqlite_path) + "-wal")
            shm_path = Path(str(sqlite_path) + "-shm")

            if wal_path.exists():
                try:
                    wal_path.unlink()
                    logger.debug("[Migration] Removed WAL file (no longer needed)")
                except Exception as e:
                    logger.debug("[Migration] Could not remove WAL file: %s", e)

            if shm_path.exists():
                try:
                    shm_path.unlink()
                    logger.debug("[Migration] Removed SHM file (no longer needed)")
                except Exception as e:
                    logger.debug("[Migration] Could not remove SHM file: %s", e)

            logger.info("[Migration] SQLite database moved to backup: %s", moved_path)
            return True

        except (OSError, PermissionError, RuntimeError) as e:
            if attempt < MOVE_RETRY_MAX_ATTEMPTS - 1:
                wait_time = (2 ** attempt) * MOVE_RETRY_INITIAL_DELAY  # Exponential backoff
                logger.warning(
                    "[Migration] Move failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1, MOVE_RETRY_MAX_ATTEMPTS, wait_time, e
                )
                time.sleep(wait_time)
            else:
                logger.error(
                    "[Migration] Failed to move SQLite database after %d attempts: %s",
                    MOVE_RETRY_MAX_ATTEMPTS, e
                )
                return False
        except Exception as e:
            logger.error("[Migration] Unexpected error moving SQLite database: %s", e)
            return False

    return False
