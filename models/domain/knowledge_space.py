"""
Knowledge Space Models for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Database models for Personal Knowledge Space feature.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import pickle
import struct

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base


class KnowledgeSpace(Base):
    """
    User's knowledge space (one per user)

    Each user has exactly one knowledge space that contains their uploaded documents.
    """

    __tablename__ = "knowledge_spaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    processing_rules: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    documents: Mapped[list["KnowledgeDocument"]] = relationship(
        "KnowledgeDocument",
        back_populates="space",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<KnowledgeSpace user_id={self.user_id}>"


class KnowledgeDocument(Base):
    """
    Uploaded document in a user's knowledge space.

    Personal-knowledge folders share MAX_DOCUMENTS_PER_USER (default 30).
    Document Summary extracts live in this table and do not consume that cap.
    """

    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    space_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_spaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(
        Enum("pending", "processing", "completed", "failed", name="document_status"),
        default="pending",
        nullable=False,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    processing_progress: Mapped[str | None] = mapped_column(String(50), nullable=True)
    processing_progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_updated_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    batch_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("document_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    doc_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    custom_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    language: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    space: Mapped["KnowledgeSpace"] = relationship("KnowledgeSpace", back_populates="documents", lazy="selectin")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    batch: Mapped["DocumentBatch | None"] = relationship(
        "DocumentBatch",
        back_populates="documents",
        foreign_keys="[KnowledgeDocument.batch_id]",
        lazy="selectin",
    )
    versions: Mapped[list["DocumentVersion"]] = relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Constraints and indexes for metadata filtering
    __table_args__ = (
        UniqueConstraint("space_id", "file_name", name="uq_space_filename"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="chk_document_status",
        ),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeDocument id={self.id} file_name={self.file_name} status={self.status}>"


class DocumentChunk(Base):
    """
    Text chunk from a document

    Chunks are used for vector search and full-text search.
    The id field is the primary key used to look up chunk text.
    """

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    document: Mapped["KnowledgeDocument"] = relationship("KnowledgeDocument", back_populates="chunks", lazy="selectin")
    attachments: Mapped[list["ChunkAttachment"]] = relationship(
        "ChunkAttachment",
        back_populates="chunk",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    child_chunks: Mapped[list["ChildChunk"]] = relationship(
        "ChildChunk",
        back_populates="parent_chunk",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Indexes for efficient queries (id index from index=True)
    __table_args__ = (Index("ix_document_chunks_document_id_chunk_index", "document_id", "chunk_index"),)

    def __repr__(self) -> str:
        return f"<DocumentChunk id={self.id} document_id={self.document_id} chunk_index={self.chunk_index}>"


class Embedding(Base):
    """
    Embedding cache for document chunks (permanent database cache like Dify).

    Stores embeddings by text hash to avoid re-computing embeddings for identical text.
    Used for document embeddings (not query embeddings - those use Redis).
    """

    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False, default="text-embedding-v4", index=True)
    provider_name: Mapped[str] = mapped_column(String(255), nullable=False, default="dashscope", index=True)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )

    # Unique constraint: same model + provider + hash = same embedding
    __table_args__ = (
        UniqueConstraint(
            "model_name",
            "provider_name",
            "hash",
            name="uq_embedding_model_provider_hash",
        ),
    )

    def set_embedding(self, embedding_data: list[float]) -> None:
        """Store embedding vector as JSON UTF-8 bytes."""
        self.embedding = json.dumps(embedding_data).encode("utf-8")

    def get_embedding(self) -> list[float]:
        """Retrieve embedding vector (JSON with legacy pickle fallback)."""
        raw = self.embedding
        if raw is None:
            return []
        if isinstance(raw, memoryview):
            raw = raw.tobytes()
        if not isinstance(raw, (bytes, bytearray)):
            return []

        # JSON format (current)
        if raw[:1] in (b"[", b"{", b'"'):
            try:
                parsed = json.loads(raw.decode("utf-8"))
                if isinstance(parsed, list):
                    return [float(x) for x in parsed]
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
                pass

        # Legacy pickle blobs
        if raw[:1] == b"\x80":
            try:
                legacy = pickle.loads(raw)
                if isinstance(legacy, list):
                    return [float(x) for x in legacy]
            except (TypeError, ValueError, struct.error, pickle.UnpicklingError):
                pass

        # Legacy struct-packed float32 array (no pickle header)
        try:
            count = len(raw) // 4
            if count > 0 and len(raw) == count * 4:
                return list(struct.unpack(f"<{count}f", raw))
        except struct.error:
            pass

        return []

    def __repr__(self) -> str:
        return f"<Embedding model={self.model_name} provider={self.provider_name} hash={self.hash[:8]}...>"


class ChunkAttachment(Base):
    """
    Attachment (images/files) linked to document chunks.

    Allows chunks to have associated files (images, PDFs, etc.) that are
    displayed with the chunk content in retrieval results.
    """

    __tablename__ = "chunk_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chunk_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)

    attachment_type: Mapped[str] = mapped_column(String(50), nullable=False, default="file")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    chunk: Mapped["DocumentChunk"] = relationship("DocumentChunk", back_populates="attachments", lazy="selectin")

    # Indexes
    __table_args__ = (Index("ix_chunk_attachments_chunk_id_position", "chunk_id", "position"),)

    def __repr__(self) -> str:
        return (
            f"<ChunkAttachment id={self.id} chunk_id={self.chunk_id} "
            f"file_name={self.file_name} type={self.attachment_type}>"
        )


class ChildChunk(Base):
    """
    Child chunk within a parent chunk (hierarchical structure).

    Used for hierarchical segmentation where parent chunks contain
    multiple child chunks for finer-grained retrieval.
    """

    __tablename__ = "child_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    parent_chunk_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)

    meta_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    parent_chunk: Mapped["DocumentChunk"] = relationship(
        "DocumentChunk", back_populates="child_chunks", lazy="selectin"
    )

    # Indexes
    __table_args__ = (Index("ix_child_chunks_parent_position", "parent_chunk_id", "position"),)

    def __repr__(self) -> str:
        return f"<ChildChunk id={self.id} parent_chunk_id={self.parent_chunk_id} position={self.position}>"


class DocumentBatch(Base):
    """
    Batch document processing tracking.

    Tracks batch uploads and processing progress for multiple documents.
    """

    __tablename__ = "document_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # File Center: a batch doubles as a named "package" of sources scoped to one diagram.
    # Legacy batches (anonymous bulk uploads) leave these NULL.
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    diagram_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("diagrams.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)

    status: Mapped[str] = mapped_column(
        Enum("pending", "processing", "completed", "failed", name="batch_status"),
        default="pending",
        nullable=False,
        index=True,
    )

    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    documents: Mapped[list["KnowledgeDocument"]] = relationship(
        "KnowledgeDocument",
        back_populates="batch",
        foreign_keys="[KnowledgeDocument.batch_id]",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentBatch id={self.id} user_id={self.user_id} "
            f"status={self.status} progress={self.completed_count}/{self.total_count}>"
        )


class DocumentVersion(Base):
    """
    Document version history.

    Tracks document versions for rollback capability.
    """

    __tablename__ = "document_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    change_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )

    document: Mapped["KnowledgeDocument"] = relationship(
        "KnowledgeDocument", back_populates="versions", lazy="selectin"
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_version"),
        Index("ix_document_versions_document_id_version", "document_id", "version_number"),
    )

    def __repr__(self) -> str:
        return f"<DocumentVersion id={self.id} document_id={self.document_id} version={self.version_number}>"
