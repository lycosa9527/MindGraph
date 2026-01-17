"""
Recovery Startup Module

Startup database integrity checks and status reporting.
"""

import logging
import os
import sys
from typing import Any, Dict

from services.infrastructure.database_recovery import DatabaseRecovery
from services.infrastructure.recovery_locks import (
    acquire_integrity_check_lock,
    release_integrity_check_lock
)

logger = logging.getLogger(__name__)


def check_database_on_startup() -> bool:
    """
    Check database integrity on startup.
    Called by main.py during lifespan initialization.

    Uses Redis distributed lock to ensure only ONE worker checks integrity.
    This prevents multiple workers from running the interactive recovery wizard
    simultaneously.

    IMPORTANT: When corruption is detected, this function ALWAYS requires
    human intervention. It will NOT automatically restore in non-interactive mode.
    This is a safety measure to prevent data loss from automated decisions.

    Performance: Uses quick_check by default for faster startup (seconds vs minutes).
    Set SKIP_INTEGRITY_CHECK=1 to skip entirely (not recommended for production).
    Set USE_FULL_INTEGRITY_CHECK=1 to use thorough check (slower but more thorough).

    Returns:
        True if startup should continue, False to abort
    """
    # Check if integrity check should be skipped (for development/testing)
    if os.getenv("SKIP_INTEGRITY_CHECK", "").lower() in ("1", "true", "yes"):
        logger.info("[Recovery] Integrity check skipped (SKIP_INTEGRITY_CHECK=1)")
        return True

    # Try to acquire lock - only one worker should check integrity
    if not acquire_integrity_check_lock():
        # Another worker is checking integrity, skip
        # Return True since integrity check will be done by another worker
        return True

    recovery = DatabaseRecovery()

    try:
        # Use quick_check by default for faster startup
        # quick_check catches most corruption issues and is much faster
        # Full integrity_check can take 2-3 minutes on databases with 2000+ users
        use_full_check = os.getenv(
            "USE_FULL_INTEGRITY_CHECK", ""
        ).lower() in ("1", "true", "yes")
        is_healthy, message = recovery.check_integrity(
            use_quick_check=not use_full_check
        )

        if is_healthy:
            logger.debug("[Recovery] %s", message)
            return True
    finally:
        # Always release lock after integrity check completes
        release_integrity_check_lock()

    # Database is corrupted - ALWAYS require human decision
    logger.error("[Recovery] DATABASE CORRUPTION DETECTED: %s", message)

    # Check if we're in interactive mode
    if sys.stdin.isatty():
        # Interactive mode - run recovery wizard
        return recovery.interactive_recovery()
    else:
        # Non-interactive mode (systemd, etc.)
        # DO NOT auto-recover - require manual intervention
        separator = "=" * 70
        logger.critical("[Recovery] %s", separator)
        logger.critical(
            "[Recovery] DATABASE CORRUPTION DETECTED - MANUAL INTERVENTION REQUIRED"
        )
        logger.critical("[Recovery] %s", separator)
        logger.critical("[Recovery] ")
        logger.critical(
            "[Recovery] The database is corrupted and requires manual recovery."
        )
        logger.critical(
            "[Recovery] Automatic recovery is DISABLED for safety - you must decide."
        )
        logger.critical("[Recovery] ")
        logger.critical("[Recovery] To recover, run the application interactively:")
        logger.critical("[Recovery]   1. Stop the service: sudo systemctl stop mindgraph")
        logger.critical("[Recovery]   2. Run manually: python run_server.py")
        logger.critical("[Recovery]   3. Follow the recovery wizard prompts")
        logger.critical("[Recovery]   4. After recovery, restart the service")
        logger.critical("[Recovery] ")

        # List available backups in logs for reference
        backups = recovery.list_backups()
        healthy_backups = [b for b in backups if b["healthy"]]

        if healthy_backups:
            logger.critical("[Recovery] Available healthy backups:")
            for backup in healthy_backups:
                users = backup.get("tables", {}).get("users", "?")
                logger.critical(
                    "[Recovery]   - %s (%s users, %s MB)",
                    backup['filename'],
                    users,
                    backup['size_mb']
                )
        else:
            logger.critical(
                "[Recovery] WARNING: No healthy backups found in backup/ directory!"
            )

        logger.critical("[Recovery] ")
        separator = "=" * 70
        logger.critical("[Recovery] %s", separator)
        logger.critical("[Recovery] Application startup ABORTED - manual recovery required")
        logger.critical("[Recovery] %s", separator)

        return False


def get_recovery_status() -> Dict[str, Any]:
    """
    Get current database and backup status.
    For API/admin panel use.

    Returns:
        dict with database health and backup info
    """
    recovery = DatabaseRecovery()

    is_healthy, message = recovery.check_integrity()
    current_stats = (
        recovery.get_database_stats(recovery.db_path)
        if recovery.db_path
        else {}
    )
    backups = recovery.list_backups()

    return {
        "database_healthy": is_healthy,
        "database_message": message,
        "database_stats": current_stats,
        "backups": backups,
        "healthy_backups_count": len([b for b in backups if b["healthy"]])
    }
