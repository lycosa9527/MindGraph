"""Storage Manager Service for Knowledge Space.

Author: lycosa9527
Made by: MindSpring Team

Monitors storage usage and performs cleanup operations.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from pathlib import Path
from typing import Dict, List, Any
import logging
import os
import shutil

from sqlalchemy.orm import Session

from models.domain.knowledge_space import KnowledgeSpace, KnowledgeDocument, DocumentChunk
from services.llm.qdrant_service import get_qdrant_service


logger = logging.getLogger(__name__)


class StorageManager:
    """
    Storage monitoring and cleanup service.

    Tracks storage usage per user and enforces limits.
    """

    def __init__(self):
        """Initialize storage manager."""
        self.storage_dir = Path(os.getenv("KNOWLEDGE_STORAGE_DIR", "./storage/knowledge_documents"))
        self.max_storage_per_user = int(os.getenv("MAX_STORAGE_PER_USER", "52428800"))  # 50MB
        self.monitor_threshold = float(os.getenv("STORAGE_MONITOR_THRESHOLD", "0.8"))  # 80%
        self.qdrant = get_qdrant_service()

    def get_user_storage_usage(self, db: Session, user_id: int) -> Dict[str, Any]:
        """
        Get storage usage for user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Dict with storage statistics
        """
        space = db.query(KnowledgeSpace).filter(
            KnowledgeSpace.user_id == user_id
        ).first()

        if not space:
            return {
                "user_id": user_id,
                "file_storage_bytes": 0,
                "file_storage_mb": 0.0,
                "document_count": 0,
                "chunk_count": 0,
                "qdrant_chunks": 0,
                "total_bytes": 0,
                "total_mb": 0.0,
                "usage_percent": 0.0,
            }

        # Calculate file storage
        user_dir = self.storage_dir / str(user_id)
        file_storage_bytes = 0
        if user_dir.exists():
            for file_path in user_dir.rglob("*"):
                if file_path.is_file():
                    file_storage_bytes += file_path.stat().st_size

        # Get document count
        document_count = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.space_id == space.id
        ).count()

        # Get chunk count
        chunk_count = db.query(DocumentChunk).join(
            KnowledgeDocument
        ).filter(
            KnowledgeDocument.space_id == space.id
        ).count()

        # Get Qdrant chunk count
        qdrant_chunks = self.qdrant.get_collection_size(user_id)

        # Estimate Qdrant storage (with SQ8 compression: ~4x smaller than uncompressed)
        # Typical embedding: 1536 dimensions x 1 byte (SQ8) = 1536 bytes + metadata overhead
        # Using ~1.6KB per chunk as estimate with SQ8 compression (includes metadata)
        qdrant_storage_bytes = qdrant_chunks * 1638

        total_bytes = file_storage_bytes + qdrant_storage_bytes
        total_mb = total_bytes / (1024 * 1024)
        usage_percent = (total_bytes / self.max_storage_per_user) * 100 if self.max_storage_per_user > 0 else 0

        return {
            "user_id": user_id,
            "file_storage_bytes": file_storage_bytes,
            "file_storage_mb": file_storage_bytes / (1024 * 1024),
            "document_count": document_count,
            "chunk_count": chunk_count,
            "qdrant_chunks": qdrant_chunks,
            "qdrant_storage_bytes": qdrant_storage_bytes,
            "qdrant_storage_mb": qdrant_storage_bytes / (1024 * 1024),
            "total_bytes": total_bytes,
            "total_mb": total_mb,
            "usage_percent": usage_percent,
        }

    def get_total_storage_usage(self, db: Session) -> Dict[str, Any]:
        """
        Get total storage usage across all users.

        Args:
            db: Database session

        Returns:
            Dict with total storage statistics
        """
        # Get all users with knowledge spaces
        spaces = db.query(KnowledgeSpace).all()

        total_file_storage = 0
        total_chunks = 0
        total_documents = 0
        total_qdrant_chunks = 0

        for space in spaces:
            user_dir = self.storage_dir / str(space.user_id)
            if user_dir.exists():
                for file_path in user_dir.rglob("*"):
                    if file_path.is_file():
                        total_file_storage += file_path.stat().st_size

            doc_count = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.space_id == space.id
            ).count()
            total_documents += doc_count

            qdrant_chunks = self.qdrant.get_collection_size(space.user_id)
            total_qdrant_chunks += qdrant_chunks

        # Get total chunk count
        total_chunks = db.query(DocumentChunk).count()

        # Estimate Qdrant storage (with SQ8 compression: ~4x smaller)
        # Typical embedding: 1536 dimensions x 1 byte (SQ8) = 1536 bytes + metadata overhead
        total_qdrant_storage = total_qdrant_chunks * 1638
        total_bytes = total_file_storage + total_qdrant_storage

        return {
            "total_file_storage_mb": total_file_storage / (1024 * 1024),
            "total_qdrant_storage_mb": total_qdrant_storage / (1024 * 1024),
            "total_storage_mb": total_bytes / (1024 * 1024),
            "total_documents": total_documents,
            "total_chunks": total_chunks,
            "total_qdrant_chunks": total_qdrant_chunks,
            "user_count": len(spaces),
        }

    def check_storage_limit(self, db: Session, user_id: int) -> bool:
        """
        Check if user has exceeded storage limit.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            True if under limit, False if exceeded
        """
        usage = self.get_user_storage_usage(db, user_id)
        return usage["total_bytes"] < self.max_storage_per_user

    def cleanup_orphaned_files(self, db: Session) -> int:
        """
        Cleanup orphaned files (files without database records).

        Args:
            db: Database session

        Returns:
            Number of files deleted
        """
        deleted_count = 0

        if not self.storage_dir.exists():
            return 0

        # Get all user directories
        for user_dir in self.storage_dir.iterdir():
            if not user_dir.is_dir():
                continue

            try:
                user_id = int(user_dir.name)
            except ValueError:
                continue

            # Check if user has knowledge space
            space = db.query(KnowledgeSpace).filter(
                KnowledgeSpace.user_id == user_id
            ).first()

            if not space:
                # User has no knowledge space, delete directory
                try:
                    shutil.rmtree(user_dir)
                    deleted_count += 1
                    logger.info("[StorageManager] Deleted orphaned directory for user %s", user_id)
                except Exception as e:
                    logger.error("[StorageManager] Failed to delete orphaned directory %s: %s", user_dir, e)
                continue

            # Get all document file paths from database
            documents = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.space_id == space.id
            ).all()
            valid_paths = {Path(doc.file_path) for doc in documents if doc.file_path}

            # Check files in directory
            for file_path in user_dir.rglob("*"):
                if file_path.is_file() and file_path not in valid_paths:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                        logger.debug("[StorageManager] Deleted orphaned file: %s", file_path)
                    except Exception as e:
                        logger.error("[StorageManager] Failed to delete orphaned file %s: %s", file_path, e)

        return deleted_count

    def get_storage_alerts(self, db: Session) -> List[Dict[str, Any]]:
        """
        Get storage alerts for users exceeding threshold.

        Args:
            db: Database session

        Returns:
            List of alert dicts
        """
        alerts = []
        spaces = db.query(KnowledgeSpace).all()

        for space in spaces:
            usage = self.get_user_storage_usage(db, space.user_id)
            if usage["usage_percent"] >= (self.monitor_threshold * 100):
                alerts.append({
                    "user_id": space.user_id,
                    "usage_percent": usage["usage_percent"],
                    "total_mb": usage["total_mb"],
                    "max_mb": self.max_storage_per_user / (1024 * 1024),
                })

        return alerts


def _create_storage_manager_getter():
    """Create storage manager getter with closure-based singleton."""
    instance = None

    def _getter() -> StorageManager:
        """Get global storage manager instance."""
        nonlocal instance
        if instance is None:
            instance = StorageManager()
        return instance

    return _getter


get_storage_manager = _create_storage_manager_getter()
