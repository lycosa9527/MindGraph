"""Document versioning helper functions.

Extracted from knowledge_space_service.py to reduce complexity.
"""
import logging
import shutil
from pathlib import Path
from typing import List

from sqlalchemy import and_
from sqlalchemy.orm import Session

from models.domain.knowledge_space import KnowledgeDocument, KnowledgeSpace, DocumentVersion


logger = logging.getLogger(__name__)


def rollback_document(
    db: Session,
    user_id: int,
    document_id: int,
    version_number: int,
    storage_dir: Path,
    reindex_chunks_func
) -> KnowledgeDocument:
    """
    Rollback document to a previous version.

    Args:
        db: Database session
        user_id: User ID
        document_id: Document ID
        version_number: Version number to rollback to
        storage_dir: Storage directory path
        reindex_chunks_func: Function to reindex chunks

    Returns:
        Rolled back KnowledgeDocument instance
    """
    # Verify ownership
    document = db.query(KnowledgeDocument).join(KnowledgeSpace).filter(
        and_(
            KnowledgeDocument.id == document_id,
            KnowledgeSpace.user_id == user_id
        )
    ).first()

    if not document:
        raise ValueError(f"Document {document_id} not found or access denied")

    # Get version
    version = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == document_id,
        DocumentVersion.version_number == version_number
    ).first()

    if not version:
        raise ValueError(f"Version {version_number} not found for document {document_id}")

    # Check if version file exists
    if not Path(version.file_path).exists():
        raise ValueError(f"Version file not found: {version.file_path}")

    try:
        # Update document status
        document.status = 'processing'
        document.processing_progress = 'rollback'
        document.processing_progress_percent = 0
        db.commit()

        # Copy version file to document location
        user_dir = storage_dir / str(user_id)
        final_path = user_dir / f"{document.id}_{document.file_name}"
        shutil.copy2(version.file_path, final_path)
        document.file_path = str(final_path)
        document.last_updated_hash = version.file_hash
        document.version += 1
        db.commit()

        # Reindex from version file
        reindex_chunks_func(document, version.file_hash)

        logger.info("[KnowledgeSpace] Rolled back document %s to version %s", document_id, version_number)
        return document

    except Exception as e:
        logger.error("[KnowledgeSpace] Failed to rollback document %s: %s", document_id, e)
        document.status = 'failed'
        document.error_message = str(e)
        document.processing_progress = None
        document.processing_progress_percent = 0
        db.commit()
        raise


def get_document_versions(
    db: Session,
    user_id: int,
    document_id: int
) -> List[DocumentVersion]:
    """
    Get all versions for a document.

    Args:
        db: Database session
        user_id: User ID
        document_id: Document ID

    Returns:
        List of DocumentVersion instances
    """
    # Verify ownership
    document = db.query(KnowledgeDocument).join(KnowledgeSpace).filter(
        and_(
            KnowledgeDocument.id == document_id,
            KnowledgeSpace.user_id == user_id
        )
    ).first()

    if not document:
        raise ValueError(f"Document {document_id} not found or access denied")

    return db.query(DocumentVersion).filter(
        DocumentVersion.document_id == document_id
    ).order_by(DocumentVersion.version_number.desc()).all()
