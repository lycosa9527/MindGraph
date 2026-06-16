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
from typing import TYPE_CHECKING
import pickle
import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
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

if TYPE_CHECKING:
    from models.domain.auth import User


def generate_uuid() -> str:
    """Generate a UUID string for session IDs."""
    return str(uuid.uuid4())


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
    queries: Mapped[list["KnowledgeQuery"]] = relationship("KnowledgeQuery", back_populates="space", lazy="selectin")
    query_templates: Mapped[list["QueryTemplate"]] = relationship(
        "QueryTemplate", back_populates="space", lazy="selectin"
    )
    evaluation_datasets: Mapped[list["EvaluationDataset"]] = relationship(
        "EvaluationDataset", back_populates="space", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<KnowledgeSpace user_id={self.user_id}>"


class KnowledgeDocument(Base):
    """
    Uploaded document in user's knowledge space

    Max 5 documents per user. Documents are processed asynchronously.
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
    outgoing_relationships: Mapped[list["DocumentRelationship"]] = relationship(
        "DocumentRelationship",
        back_populates="source_document",
        foreign_keys="[DocumentRelationship.source_document_id]",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    incoming_relationships: Mapped[list["DocumentRelationship"]] = relationship(
        "DocumentRelationship",
        back_populates="target_document",
        foreign_keys="[DocumentRelationship.target_document_id]",
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
    The id field serves dual purpose:
    - Primary key in database for text lookup
    - Point ID in Qdrant for vector lookup
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

    # Indexes for efficient queries (id index from index=True; used for Qdrant lookup)
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
        """Store embedding vector (pickled)."""
        self.embedding = pickle.dumps(embedding_data, protocol=pickle.HIGHEST_PROTOCOL)

    def get_embedding(self) -> list[float]:
        """Retrieve embedding vector (unpickled)."""
        return pickle.loads(self.embedding)

    def __repr__(self) -> str:
        return f"<Embedding model={self.model_name} provider={self.provider_name} hash={self.hash[:8]}...>"


class KnowledgeQuery(Base):
    """
    Query recording for Knowledge Space analytics (like Dify's DatasetQuery).

    Records all retrieval queries for analytics, optimization, and insights.
    """

    __tablename__ = "knowledge_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    space_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_spaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    query: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(String(50), nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    score_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    embedding_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    search_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    rerank_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped[str] = mapped_column(String(100), nullable=False, default="api")
    source_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )

    space: Mapped["KnowledgeSpace"] = relationship("KnowledgeSpace", back_populates="queries", lazy="selectin")
    feedbacks: Mapped[list["QueryFeedback"]] = relationship(
        "QueryFeedback",
        back_populates="query",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    evaluation_results: Mapped[list["EvaluationResult"]] = relationship(
        "EvaluationResult", back_populates="query", lazy="selectin"
    )

    # Indexes for analytics queries
    __table_args__ = (
        Index("ix_knowledge_queries_user_id_created_at", "user_id", "created_at"),
        Index("ix_knowledge_queries_method", "method"),
        Index("ix_knowledge_queries_source", "source"),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeQuery id={self.id} user_id={self.user_id} query={self.query[:30]}... method={self.method}>"


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


class QueryFeedback(Base):
    """
    Query feedback for learning and optimization.

    Records user feedback on retrieval results to improve query quality.
    """

    __tablename__ = "query_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    query_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_queries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    space_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_spaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    feedback_type: Mapped[str] = mapped_column(
        Enum("positive", "negative", "neutral", name="feedback_type"),
        nullable=False,
        index=True,
    )
    feedback_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    relevant_chunk_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    irrelevant_chunk_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )

    query: Mapped["KnowledgeQuery"] = relationship("KnowledgeQuery", back_populates="feedbacks", lazy="selectin")

    def __repr__(self) -> str:
        return f"<QueryFeedback id={self.id} query_id={self.query_id} type={self.feedback_type}>"


class QueryTemplate(Base):
    """
    Query templates for saved queries.

    Allows users to save and reuse common queries.
    """

    __tablename__ = "query_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    space_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("knowledge_spaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    space: Mapped["KnowledgeSpace | None"] = relationship(
        "KnowledgeSpace", back_populates="query_templates", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<QueryTemplate id={self.id} name={self.name} usage={self.usage_count}>"


class DocumentRelationship(Base):
    """
    Relationships between documents.

    Supports document linking, references, citations, and cross-document retrieval.
    """

    __tablename__ = "document_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )

    source_document: Mapped["KnowledgeDocument"] = relationship(
        "KnowledgeDocument",
        foreign_keys=[source_document_id],
        back_populates="outgoing_relationships",
        lazy="selectin",
    )
    target_document: Mapped["KnowledgeDocument"] = relationship(
        "KnowledgeDocument",
        foreign_keys=[target_document_id],
        back_populates="incoming_relationships",
        lazy="selectin",
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "source_document_id",
            "target_document_id",
            "relationship_type",
            name="uq_document_relationship",
        ),
        Index(
            "ix_document_relationships_source_target",
            "source_document_id",
            "target_document_id",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentRelationship id={self.id} "
            f"source={self.source_document_id} -> target={self.target_document_id} "
            f"type={self.relationship_type}>"
        )


class EvaluationDataset(Base):
    """
    Evaluation dataset for retrieval quality measurement.

    Contains queries with expected results for quality metrics calculation.
    """

    __tablename__ = "evaluation_datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    space_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("knowledge_spaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    queries: Mapped[list] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    space: Mapped["KnowledgeSpace | None"] = relationship(
        "KnowledgeSpace", back_populates="evaluation_datasets", lazy="selectin"
    )
    results: Mapped[list["EvaluationResult"]] = relationship(
        "EvaluationResult",
        back_populates="dataset",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        query_count = len(self.queries) if self.queries is not None else 0
        return f"<EvaluationDataset id={self.id} name={self.name} queries={query_count}>"


class EvaluationResult(Base):
    """
    Evaluation result for a query in a dataset.

    Stores quality metrics for retrieval evaluation.
    """

    __tablename__ = "evaluation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dataset_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("evaluation_datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("knowledge_queries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)

    method: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )

    dataset: Mapped["EvaluationDataset"] = relationship("EvaluationDataset", back_populates="results", lazy="selectin")
    query: Mapped["KnowledgeQuery | None"] = relationship(
        "KnowledgeQuery", back_populates="evaluation_results", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<EvaluationResult id={self.id} dataset_id={self.dataset_id} method={self.method}>"


class ChunkTestResult(Base):
    """
    Chunk test result for comparing chunking methods.

    Stores results from RAG chunk testing comparing semchunk vs mindchunk.
    Uses UUID for session_id to enable secure, non-guessable session tracking.
    """

    __tablename__ = "chunk_test_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, default=generate_uuid)
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    document_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    semchunk_chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mindchunk_chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_stats: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    retrieval_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    comparison_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    evaluation_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[str] = mapped_column(
        Enum("pending", "processing", "completed", "failed", name="chunk_test_status"),
        default="pending",
        nullable=False,
        index=True,
    )
    current_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_methods: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )

    user: Mapped["User"] = relationship("User", backref="chunk_test_results", lazy="selectin")

    @property
    def processing_progress(self) -> str | None:
        """
        Get standardized progress string format compatible with ChunkTestDocument.

        Returns:
            Progress string in format "stage (method)" or "stage"
        """
        if self.current_stage is None:
            return None

        if self.current_method is not None:
            return f"{self.current_stage} ({self.current_method})"
        return self.current_stage

    @property
    def processing_progress_percent(self) -> int:
        """
        Get progress percentage (alias for progress_percent for consistency).

        Returns:
            Progress percentage (0-100)
        """
        return self.progress_percent

    def __repr__(self) -> str:
        return f"<ChunkTestResult id={self.id} user_id={self.user_id} dataset_name={self.dataset_name}>"


class ChunkTestDocument(Base):
    """
    Document uploaded specifically for chunk testing.

    Separate from KnowledgeDocument - these are temporary test documents
    that don't interfere with the user's knowledge space.
    Max 5 documents per user for testing purposes.
    """

    __tablename__ = "chunk_test_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(
        Enum(
            "pending",
            "processing",
            "completed",
            "failed",
            name="chunk_test_document_status",
        ),
        default="pending",
        nullable=False,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    processing_progress: Mapped[str | None] = mapped_column(String(50), nullable=True)
    processing_progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meta_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", backref="chunk_test_documents", lazy="selectin")
    chunks: Mapped[list["ChunkTestDocumentChunk"]] = relationship(
        "ChunkTestDocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="chk_chunk_test_document_status",
        ),
        Index("ix_chunk_test_documents_user_id_status", "user_id", "status"),
    )

    @property
    def progress_percent(self) -> int:
        """
        Get progress percentage (alias for processing_progress_percent for consistency).

        Returns:
            Progress percentage (0-100)
        """
        return self.processing_progress_percent

    def __repr__(self) -> str:
        return f"<ChunkTestDocument id={self.id} file_name={self.file_name} status={self.status}>"


class ChunkTestDocumentChunk(Base):
    """
    Text chunk from a chunk test document.

    Separate from DocumentChunk - these chunks are only used for testing.
    """

    __tablename__ = "chunk_test_document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chunk_test_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)

    chunking_method: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    meta_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    document: Mapped["ChunkTestDocument"] = relationship("ChunkTestDocument", back_populates="chunks", lazy="selectin")

    # Indexes for efficient queries (chunking_method single-column index from index=True)
    __table_args__ = (
        Index(
            "ix_chunk_test_document_chunks_document_id_chunk_index",
            "document_id",
            "chunk_index",
        ),
        Index(
            "ix_chunk_test_document_chunks_document_method",
            "document_id",
            "chunking_method",
        ),
    )

    def __repr__(self) -> str:
        return f"<ChunkTestDocumentChunk id={self.id} document_id={self.document_id} chunk_index={self.chunk_index}>"
