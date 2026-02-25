"""
Recovery Startup Module

Startup database integrity checks and status reporting.
"""

import logging
import os
import sys
from typing import Any, Dict

from config.database import recover_from_kill_9, SessionLocal, check_integrity, engine, DATABASE_URL
from models.domain.knowledge_space import ChunkTestDocument
from services.infrastructure.monitoring.critical_alert import CriticalAlertService
from services.infrastructure.recovery.database_recovery import DatabaseRecovery
from services.infrastructure.recovery.recovery_locks import (
    acquire_integrity_check_lock,
    release_integrity_check_lock
)
from services.knowledge.chunk_test_document_service import ChunkTestDocumentService
from services.utils.backup_scheduler import get_backup_status
from sqlalchemy import text

logger = logging.getLogger(__name__)


def cleanup_incomplete_chunk_operations() -> int:
    """
    Clean up incomplete chunk operations after kill -9.

    Detects documents stuck in 'processing' status and:
    1. Cleans up partial Qdrant data
    2. Deletes partial chunks from database
    3. Resets status to 'pending' for retry

    Returns:
        Number of documents cleaned up
    """
    try:
        db = SessionLocal()
        cleaned_count = 0

        try:
            # Find all documents stuck in 'processing' status
            stuck_docs = db.query(ChunkTestDocument).filter(
                ChunkTestDocument.status == 'processing'
            ).all()

            if not stuck_docs:
                logger.debug("[Recovery] No documents stuck in processing status")
                return 0

            logger.info(
                "[Recovery] Found %d document(s) stuck in 'processing' status, cleaning up...",
                len(stuck_docs)
            )

            # Group by user_id to create service instances efficiently
            docs_by_user = {}
            for doc in stuck_docs:
                if doc.user_id not in docs_by_user:
                    docs_by_user[doc.user_id] = []
                docs_by_user[doc.user_id].append(doc)

            # Clean up each document
            for user_id, docs in docs_by_user.items():
                try:
                    service = ChunkTestDocumentService(db, user_id)
                    for doc in docs:
                        try:
                            service.cleanup_incomplete_processing(doc.id)
                            cleaned_count += 1
                            logger.info(
                                "[Recovery] Cleaned up incomplete processing for document %s (user %s)",
                                doc.id, user_id
                            )
                        except Exception as e:
                            logger.error(
                                "[Recovery] Failed to cleanup document %s: %s",
                                doc.id, e,
                                exc_info=True
                            )
                except Exception as e:
                    logger.error(
                        "[Recovery] Failed to create service for user %s: %s",
                        user_id, e,
                        exc_info=True
                    )

            if cleaned_count > 0:
                logger.info(
                    "[Recovery] Successfully cleaned up %d incomplete chunk operation(s)",
                    cleaned_count
                )

            return cleaned_count

        except Exception as e:
            logger.error(
                "[Recovery] Error during incomplete chunk operations cleanup: %s",
                e,
                exc_info=True
            )
            db.rollback()
            return 0
        finally:
            db.close()

    except ImportError as e:
        logger.debug(
            "[Recovery] Could not import chunk test models (may not be available): %s",
            e
        )
        return 0
    except Exception as e:
        logger.warning(
            "[Recovery] Error during incomplete chunk operations cleanup: %s",
            e
        )
        return 0


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
    Set SKIP_INTEGRITY_CHECK=true to skip entirely (not recommended for production).
    Set DB_QUICK_CHECK_ENABLED=false to use full integrity_check (slower but more thorough).
    Set USE_FULL_INTEGRITY_CHECK=true to use thorough check (deprecated, use DB_QUICK_CHECK_ENABLED=false).

    Returns:
        True if startup should continue, False to abort
    """
    # First, recover from potential kill -9 scenarios
    # This clears stale locks and connections before integrity check
    logger.debug("[Recovery] Recovering from potential kill -9 scenario...")
    recovery_success = recover_from_kill_9()
    if not recovery_success:
        logger.warning(
            "[Recovery] Database recovery from kill -9 failed, "
            "but continuing with integrity check"
        )

    # Clean up incomplete chunk operations (Qdrant + database)
    # This abandons partial work and resets documents to 'pending' for retry
    logger.debug("[Recovery] Cleaning up incomplete chunk operations...")
    cleaned_count = cleanup_incomplete_chunk_operations()
    if cleaned_count > 0:
        logger.info(
            "[Recovery] Cleaned up %d incomplete chunk operation(s) from kill -9",
            cleaned_count
        )

    # Check if integrity check should be skipped (for development/testing)
    skip_check_env = os.getenv("SKIP_INTEGRITY_CHECK", "")
    logger.debug("[Recovery] SKIP_INTEGRITY_CHECK=%s", skip_check_env)
    if skip_check_env.lower() in ("true", "yes"):
        logger.debug("[Recovery] Integrity check skipped (SKIP_INTEGRITY_CHECK=true)")
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
        # Check DB_QUICK_CHECK_ENABLED first (new preferred way)
        db_quick_check_env = os.getenv("DB_QUICK_CHECK_ENABLED", "true")
        quick_check_enabled = db_quick_check_env.lower() in ("true", "yes")
        # Fallback to USE_FULL_INTEGRITY_CHECK for backward compatibility
        use_full_int_check_env = os.getenv("USE_FULL_INTEGRITY_CHECK", "")
        use_full_check = use_full_int_check_env.lower() in ("true", "yes")
        # Use quick_check if enabled AND not forcing full check
        use_quick_check = quick_check_enabled and not use_full_check
        logger.debug(
            "[Recovery] Environment: DB_QUICK_CHECK_ENABLED=%s, USE_FULL_INTEGRITY_CHECK=%s",
            db_quick_check_env,
            use_full_int_check_env
        )
        logger.info(
            "[Recovery] Integrity check: using quick_check=%s",
            use_quick_check
        )
        is_healthy, message = recovery.check_integrity(
            use_quick_check=use_quick_check
        )

        if is_healthy:
            logger.debug("[Recovery] %s", message)
            return True
    finally:
        # Always release lock after integrity check completes
        release_integrity_check_lock()

    # Database is corrupted - ALWAYS require human decision
    logger.error("[Recovery] DATABASE CORRUPTION DETECTED: %s", message)

    # Send critical alert for database corruption
    try:
        CriticalAlertService.send_startup_failure_alert_sync(
            component="Database",
            error_message=f"Database corruption detected: {message}",
            details="Database integrity check failed. Manual recovery required. Check logs for details."
        )
    except Exception as alert_error:  # pylint: disable=broad-except
        logger.error("[Recovery] Failed to send database corruption alert: %s", alert_error)

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
        logger.critical("[Recovery]   2. Run manually: python main.py")
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
    # Use database-agnostic integrity check
    is_healthy = check_integrity()
    
    if is_healthy:
        message = "Database connection and integrity check passed"
    else:
        message = "Database integrity check failed"

    # Get basic database stats (database-agnostic)
    current_stats = {}
    try:
        # For PostgreSQL, get database size using pg_database_size
        if "postgresql" in DATABASE_URL.lower():
            with engine.connect() as conn:
                # Extract database name from URL
                db_name = DATABASE_URL.split("/")[-1].split("?")[0]
                result = conn.execute(
                    text("SELECT pg_size_pretty(pg_database_size(:db_name)) as size"),
                    {"db_name": db_name}
                )
                size_row = result.fetchone()
                if size_row:
                    current_stats = {
                        "database_url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,
                        "size": size_row[0] if size_row else "unknown"
                    }
        else:
            # For other databases, just show connection URL (masked)
            current_stats = {
                "database_url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
            }
    except Exception as e:  # pylint: disable=broad-except
        logger.debug("Failed to get database stats: %s", e)
        # Stats are optional, continue without them

    # Get backup status from backup scheduler (already PostgreSQL-only)
    backup_status = get_backup_status()
    backups = backup_status.get("backups", [])

    return {
        "database_healthy": is_healthy,
        "database_message": message,
        "database_stats": current_stats,
        "backups": backups,
        "healthy_backups_count": len(backups)  # All PostgreSQL backups are considered healthy
    }
