"""
Recovery Startup Module

Startup PostgreSQL connectivity checks, kill-9 recovery, and status reporting.
"""

import logging
import os
from typing import Any, Dict

from sqlalchemy import text

from config.database import (
    recover_from_kill_9,
    SessionLocal,
    check_integrity,
    engine,
    DATABASE_URL,
)
from models.domain.knowledge_space import ChunkTestDocument
from services.infrastructure.monitoring.critical_alert import CriticalAlertService
from services.infrastructure.recovery.recovery_locks import (
    acquire_integrity_check_lock,
    release_integrity_check_lock,
)
from services.knowledge.chunk_test_document_service import ChunkTestDocumentService
from services.utils.backup_scheduler import get_backup_status

logger = logging.getLogger(__name__)


def _cleanup_user_documents(db, user_id, docs) -> int:
    """Clean up stuck documents for a single user. Returns count cleaned."""
    cleaned = 0
    try:
        service = ChunkTestDocumentService(db, user_id)
    except Exception as exc:
        logger.error(
            "[Recovery] Failed to create service for user %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        return 0

    for doc in docs:
        try:
            service.cleanup_incomplete_processing(doc.id)
            cleaned += 1
            logger.info(
                "[Recovery] Cleaned up incomplete processing for document %s (user %s)",
                doc.id,
                user_id,
            )
        except Exception as exc:
            logger.error(
                "[Recovery] Failed to cleanup document %s: %s",
                doc.id,
                exc,
                exc_info=True,
            )
    return cleaned


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
    except ImportError as exc:
        logger.debug(
            "[Recovery] Could not import chunk test models (may not be available): %s",
            exc,
        )
        return 0
    except Exception as exc:
        logger.warning(
            "[Recovery] Error during incomplete chunk operations cleanup: %s",
            exc,
        )
        return 0

    try:
        stuck_docs = db.query(ChunkTestDocument).filter(ChunkTestDocument.status == "processing").all()

        if not stuck_docs:
            logger.debug("[Recovery] No documents stuck in processing status")
            return 0

        logger.info(
            "[Recovery] Found %d document(s) stuck in 'processing' status, cleaning up...",
            len(stuck_docs),
        )

        docs_by_user: Dict[Any, list] = {}
        for doc in stuck_docs:
            docs_by_user.setdefault(doc.user_id, []).append(doc)

        cleaned_count = sum(_cleanup_user_documents(db, uid, docs) for uid, docs in docs_by_user.items())

        if cleaned_count > 0:
            logger.info(
                "[Recovery] Successfully cleaned up %d incomplete chunk operation(s)",
                cleaned_count,
            )
        return cleaned_count

    except Exception as exc:
        logger.error(
            "[Recovery] Error during incomplete chunk operations cleanup: %s",
            exc,
            exc_info=True,
        )
        db.rollback()
        return 0
    finally:
        db.close()


def check_database_on_startup() -> bool:
    """
    Check PostgreSQL connectivity on startup.

    Called by main.py during lifespan initialization.
    Uses Redis distributed lock to ensure only ONE worker runs the check.

    Set SKIP_INTEGRITY_CHECK=true to skip entirely (for development/testing).

    Returns:
        True if startup should continue, False to abort
    """
    logger.debug("[Recovery] Recovering from potential kill -9 scenario...")
    recovery_success = recover_from_kill_9()
    if not recovery_success:
        logger.warning("[Recovery] Database recovery from kill -9 failed, but continuing with connectivity check")

    logger.debug("[Recovery] Cleaning up incomplete chunk operations...")
    cleaned_count = cleanup_incomplete_chunk_operations()
    if cleaned_count > 0:
        logger.info(
            "[Recovery] Cleaned up %d incomplete chunk operation(s) from kill -9",
            cleaned_count,
        )

    skip_check_env = os.getenv("SKIP_INTEGRITY_CHECK", "")
    if skip_check_env.lower() in ("true", "yes"):
        logger.debug("[Recovery] Integrity check skipped (SKIP_INTEGRITY_CHECK=true)")
        return True

    if not acquire_integrity_check_lock():
        return True

    try:
        is_healthy = check_integrity()
        if is_healthy:
            logger.info("[Recovery] PostgreSQL connectivity check passed")
            return True
    finally:
        release_integrity_check_lock()

    logger.error("[Recovery] PostgreSQL connectivity check FAILED")

    try:
        CriticalAlertService.send_startup_failure_alert_sync(
            component="Database",
            error_message="PostgreSQL connectivity check failed",
            details=("Cannot connect to PostgreSQL. Check DATABASE_URL, PostgreSQL service status, and pg_hba.conf."),
        )
    except Exception as alert_error:
        logger.error("[Recovery] Failed to send database alert: %s", alert_error)

    backup_status = get_backup_status()
    backups = backup_status.get("backups", [])

    separator = "=" * 70
    logger.critical("[Recovery] %s", separator)
    logger.critical("[Recovery] POSTGRESQL UNREACHABLE - STARTUP ABORTED")
    logger.critical("[Recovery] %s", separator)
    logger.critical("[Recovery] ")
    logger.critical("[Recovery] Cannot connect to PostgreSQL. Verify:")
    logger.critical("[Recovery]   1. PostgreSQL service is running")
    logger.critical("[Recovery]   2. DATABASE_URL is correct")
    logger.critical("[Recovery]   3. pg_hba.conf allows connections")
    logger.critical("[Recovery] ")

    if backups:
        logger.critical("[Recovery] Available backups for restore:")
        for backup in backups:
            logger.critical(
                "[Recovery]   - %s (%.2f MB, %s)",
                backup.get("filename", "?"),
                backup.get("size_mb", 0),
                backup.get("type", "postgresql"),
            )
    else:
        logger.critical("[Recovery] No backups found in backup/ directory.")

    logger.critical("[Recovery] ")
    logger.critical("[Recovery] %s", separator)

    return False


def get_recovery_status() -> Dict[str, Any]:
    """
    Get current PostgreSQL database and backup status.
    For API/admin panel use.

    Returns:
        dict with database health and backup info
    """
    is_healthy = check_integrity()
    message = "PostgreSQL connection check passed" if is_healthy else "PostgreSQL connection check failed"

    current_stats: Dict[str, Any] = {}
    try:
        with engine.connect() as conn:
            db_name = DATABASE_URL.split("/")[-1].split("?")[0]
            result = conn.execute(
                text("SELECT pg_size_pretty(pg_database_size(:db_name)) as size"),
                {"db_name": db_name},
            )
            size_row = result.fetchone()
            if size_row:
                masked_url = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
                current_stats = {
                    "database_url": masked_url,
                    "size": size_row[0],
                }
    except Exception as exc:
        logger.debug("Failed to get database stats: %s", exc)

    backup_status = get_backup_status()
    backups = backup_status.get("backups", [])

    return {
        "database_healthy": is_healthy,
        "database_message": message,
        "database_stats": current_stats,
        "backups": backups,
        "healthy_backups_count": len(backups),
    }
