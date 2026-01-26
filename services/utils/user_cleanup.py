"""
User Cleanup Service for Knowledge Space
Author: lycosa9527
Made by: MindSpring Team

Cleanup function for user deletion (deletes documents, chunks, Qdrant collection, files).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from models.domain.knowledge_space import KnowledgeSpace
from services.llm.qdrant_service import get_qdrant_service

logger = logging.getLogger(__name__)


def cleanup_user_knowledge_space(db: Session, user_id: int) -> None:
    """
    Cleanup user's knowledge space on user deletion.

    Deletes:
    - All documents from database
    - All chunks from database
    - Qdrant collection
    - File storage directory

    Args:
        db: Database session
        user_id: User ID to cleanup
    """
    try:
        # Get knowledge space
        space = db.query(KnowledgeSpace).filter(
            KnowledgeSpace.user_id == user_id
        ).first()

        if not space:
            logger.debug("[UserCleanup] No knowledge space found for user %s", user_id)
            return

        # Delete Qdrant collection
        try:
            qdrant = get_qdrant_service()
            qdrant.delete_user_collection(user_id)
            logger.info("[UserCleanup] Deleted Qdrant collection for user %s", user_id)
        except Exception as e:
            logger.error("[UserCleanup] Failed to delete Qdrant collection for user %s: %s", user_id, e)

        # Delete files
        storage_dir = Path(os.getenv("KNOWLEDGE_STORAGE_DIR", "./storage/knowledge_documents"))
        user_dir = storage_dir / str(user_id)

        if user_dir.exists():
            try:
                shutil.rmtree(user_dir)
                logger.info("[UserCleanup] Deleted file storage for user %s", user_id)
            except Exception as e:
                logger.error("[UserCleanup] Failed to delete file storage for user %s: %s", user_id, e)

        # Delete database records (cascade will handle chunks)
        db.delete(space)
        db.commit()

        logger.info("[UserCleanup] Cleaned up knowledge space for user %s", user_id)

    except Exception as e:
        logger.error("[UserCleanup] Failed to cleanup knowledge space for user %s: %s", user_id, e)
        db.rollback()
        raise
