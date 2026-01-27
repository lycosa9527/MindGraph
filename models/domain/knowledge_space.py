"""
Knowledge Space Models for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Database models for Personal Knowledge Space feature.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from datetime import datetime
from typing import Optional
import pickle
import uuid

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, JSON, Enum, Index,
    CheckConstraint, UniqueConstraint, LargeBinary, Float
)
from sqlalchemy.orm import relationship

from models.domain.auth import Base


def generate_uuid():
    """Generate a UUID string for session IDs."""
    return str(uuid.uuid4())



class KnowledgeSpace(Base):
    """
    User's knowledge space (one per user)

    Each user has exactly one knowledge space that contains their uploaded documents.
    """
    __tablename__ = "knowledge_spaces"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    # Processing rules configuration (JSON)
    # Format: {
    #   "mode": "automatic" | "custom",
    #   "chunking_strategy": "recursive" | "semantic" | "sentence" | "table" | "code" | "hybrid",
    #   "rules": {
    #     "segmentation": {
    #       "max_tokens": 500,
    #       "chunk_overlap": 50,
    #       "separator": "\n\n"
    #     },
    #     "pre_processing_rules": [
    #       {"id": "remove_extra_spaces", "enabled": true},
    #       {"id": "remove_urls_emails", "enabled": false}
    #     ]
    #   }
    # }
    processing_rules = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    documents = relationship("KnowledgeDocument", back_populates="space", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<KnowledgeSpace user_id={self.user_id}>"


class KnowledgeDocument(Base):
    """
    Uploaded document in user's knowledge space

    Max 5 documents per user. Documents are processed asynchronously.
    """
    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, index=True)
    space_id = Column(Integer, ForeignKey("knowledge_spaces.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # Storage path
    file_type = Column(String(100), nullable=False)  # MIME type
    file_size = Column(Integer, nullable=False)  # Bytes

    # Processing status
    status = Column(
        Enum('pending', 'processing', 'completed', 'failed', name='document_status'),
        default='pending',
        nullable=False,
        index=True
    )
    error_message = Column(Text, nullable=True)  # Error details if failed
    processing_task_id = Column(String(255), nullable=True)  # Celery task ID
    # Current processing stage: 'extracting', 'cleaning', 'chunking', 'embedding', 'indexing'
    processing_progress = Column(String(50), nullable=True)
    processing_progress_percent = Column(Integer, default=0, nullable=False)  # Progress percentage 0-100

    # Processing results
    chunk_count = Column(Integer, default=0, nullable=False)

    # Version tracking (for future versioning feature)
    version = Column(Integer, default=1, nullable=False)  # Document version number
    last_updated_hash = Column(String(64), nullable=True)  # Hash of last updated content for change detection

    # Batch processing
    batch_id = Column(Integer, ForeignKey("document_batches.id", ondelete="SET NULL"), nullable=True, index=True)

    # Advanced metadata
    # Custom metadata dict (renamed from 'metadata' - reserved in SQLAlchemy)
    doc_metadata = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)  # Array of tag strings
    category = Column(String(100), nullable=True, index=True)  # Document category
    custom_fields = Column(JSON, nullable=True)  # User-defined custom fields

    # Language detection
    language = Column(String(10), nullable=True, index=True)  # Detected language code (e.g., 'zh', 'en', 'ja')

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    space = relationship("KnowledgeSpace", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

    # Constraints and indexes for metadata filtering
    __table_args__ = (
        UniqueConstraint('space_id', 'file_name', name='uq_space_filename'),
        CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed')", name='chk_document_status'),
        Index('ix_knowledge_documents_category', 'category'),
    )

    def __repr__(self):
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

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)  # Order within document
    text = Column(Text, nullable=False)  # Chunk content - stored in main database only

    # Position in original document
    start_char = Column(Integer, nullable=False)
    end_char = Column(Integer, nullable=False)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    document = relationship("KnowledgeDocument", back_populates="chunks")

    # Indexes for efficient queries
    __table_args__ = (
        Index('ix_document_chunks_document_id_chunk_index', 'document_id', 'chunk_index'),
        Index('ix_document_chunks_id', 'id'),  # For Qdrant lookup
    )

    def __repr__(self):
        return f"<DocumentChunk id={self.id} document_id={self.document_id} chunk_index={self.chunk_index}>"


class Embedding(Base):
    """
    Embedding cache for document chunks (permanent database cache like Dify).

    Stores embeddings by text hash to avoid re-computing embeddings for identical text.
    Used for document embeddings (not query embeddings - those use Redis).
    """
    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(255), nullable=False, default='text-embedding-v4', index=True)
    provider_name = Column(String(255), nullable=False, default='dashscope', index=True)
    hash = Column(String(64), nullable=False, index=True)  # MD5 hash of text
    embedding = Column(LargeBinary, nullable=False)  # Pickled embedding vector

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Unique constraint: same model + provider + hash = same embedding
    __table_args__ = (
        UniqueConstraint('model_name', 'provider_name', 'hash', name='uq_embedding_model_provider_hash'),
        Index('ix_embeddings_hash', 'hash'),
    )

    def set_embedding(self, embedding_data: list[float]) -> None:
        """Store embedding vector (pickled)."""
        self.embedding = pickle.dumps(embedding_data, protocol=pickle.HIGHEST_PROTOCOL)

    def get_embedding(self) -> list[float]:
        """Retrieve embedding vector (unpickled)."""
        return pickle.loads(self.embedding)

    def __repr__(self):
        return f"<Embedding model={self.model_name} provider={self.provider_name} hash={self.hash[:8]}...>"


class KnowledgeQuery(Base):
    """
    Query recording for Knowledge Space analytics (like Dify's DatasetQuery).

    Records all retrieval queries for analytics, optimization, and insights.
    """
    __tablename__ = "knowledge_queries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    space_id = Column(Integer, ForeignKey("knowledge_spaces.id", ondelete="CASCADE"), nullable=False, index=True)

    # Query details
    query = Column(Text, nullable=False)  # User's query text
    method = Column(String(50), nullable=False)  # semantic, keyword, hybrid
    top_k = Column(Integer, nullable=False)  # Requested top_k
    score_threshold = Column(Float, nullable=False, default=0.0)  # Score threshold used

    # Results
    result_count = Column(Integer, nullable=False, default=0)  # Number of results returned

    # Timing metrics (in milliseconds)
    embedding_ms = Column(Float, nullable=True)  # Embedding generation time
    search_ms = Column(Float, nullable=True)  # Search execution time
    rerank_ms = Column(Float, nullable=True)  # Reranking time
    total_ms = Column(Float, nullable=True)  # Total query time

    # Source tracking
    source = Column(String(100), nullable=False, default='api')  # api, diagram_generation, etc.
    source_context = Column(JSON, nullable=True)  # Additional context (e.g., diagram_type)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    space = relationship("KnowledgeSpace", backref="queries")

    # Indexes for analytics queries
    __table_args__ = (
        Index('ix_knowledge_queries_user_id_created_at', 'user_id', 'created_at'),
        Index('ix_knowledge_queries_method', 'method'),
        Index('ix_knowledge_queries_source', 'source'),
    )

    def __repr__(self):
        return f"<KnowledgeQuery id={self.id} user_id={self.user_id} query={self.query[:30]}... method={self.method}>"


class ChunkAttachment(Base):
    """
    Attachment (images/files) linked to document chunks.

    Allows chunks to have associated files (images, PDFs, etc.) that are
    displayed with the chunk content in retrieval results.
    """
    __tablename__ = "chunk_attachments"

    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(Integer, ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False, index=True)

    # File information (stored directly, not as foreign key to keep it simple)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # Storage path
    file_type = Column(String(100), nullable=False)  # MIME type
    file_size = Column(Integer, nullable=False)  # Bytes

    # Attachment metadata
    attachment_type = Column(String(50), nullable=False, default='file')  # 'image', 'file', 'document'
    position = Column(Integer, nullable=False, default=0)  # Order within chunk

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    chunk = relationship("DocumentChunk", backref="attachments")

    # Indexes
    __table_args__ = (
        Index('ix_chunk_attachments_chunk_id_position', 'chunk_id', 'position'),
    )

    def __repr__(self):
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

    id = Column(Integer, primary_key=True, index=True)
    parent_chunk_id = Column(Integer, ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False, index=True)

    # Content
    content = Column(Text, nullable=False)

    # Position within parent chunk
    position = Column(Integer, nullable=False, default=0)

    # Character positions in original document
    start_char = Column(Integer, nullable=False)
    end_char = Column(Integer, nullable=False)

    # Metadata
    meta_data = Column(JSON, nullable=True)  # Renamed from metadata to avoid SQLAlchemy reserved name

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    parent_chunk = relationship("DocumentChunk", backref="child_chunks")

    # Indexes
    __table_args__ = (
        Index('ix_child_chunks_parent_position', 'parent_chunk_id', 'position'),
    )

    def __repr__(self):
        return f"<ChildChunk id={self.id} parent_chunk_id={self.parent_chunk_id} position={self.position}>"


class DocumentBatch(Base):
    """
    Batch document processing tracking.

    Tracks batch uploads and processing progress for multiple documents.
    """
    __tablename__ = "document_batches"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Batch status
    status = Column(
        Enum('pending', 'processing', 'completed', 'failed', name='batch_status'),
        default='pending',
        nullable=False,
        index=True
    )

    # Progress tracking
    total_count = Column(Integer, nullable=False, default=0)
    completed_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)

    # Error information
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    documents = relationship("KnowledgeDocument", backref="batch")

    def __repr__(self):
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

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False, index=True)

    # Version file information
    file_path = Column(String(500), nullable=False)  # Path to version file
    file_hash = Column(String(64), nullable=False)  # Hash of file content

    # Version metadata
    chunk_count = Column(Integer, nullable=False, default=0)
    change_summary = Column(JSON, nullable=True)  # Summary of changes: {"added": 5, "updated": 3, "deleted": 2}

    # Version creator
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    document = relationship("KnowledgeDocument", backref="versions")

    # Constraints
    __table_args__ = (
        UniqueConstraint('document_id', 'version_number', name='uq_document_version'),
        Index('ix_document_versions_document_id_version', 'document_id', 'version_number'),
    )

    def __repr__(self):
        return f"<DocumentVersion id={self.id} document_id={self.document_id} version={self.version_number}>"


class QueryFeedback(Base):
    """
    Query feedback for learning and optimization.

    Records user feedback on retrieval results to improve query quality.
    """
    __tablename__ = "query_feedback"

    id = Column(Integer, primary_key=True, index=True)
    query_id = Column(Integer, ForeignKey("knowledge_queries.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    space_id = Column(Integer, ForeignKey("knowledge_spaces.id", ondelete="CASCADE"), nullable=False, index=True)

    # Feedback details
    feedback_type = Column(
        Enum('positive', 'negative', 'neutral', name='feedback_type'),
        nullable=False,
        index=True
    )
    feedback_score = Column(Integer, nullable=True)  # 1-5 rating

    # Relevant and irrelevant chunks
    relevant_chunk_ids = Column(JSON, nullable=True)  # Array of chunk IDs that were relevant
    irrelevant_chunk_ids = Column(JSON, nullable=True)  # Array of chunk IDs that were irrelevant

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    query = relationship("KnowledgeQuery", backref="feedbacks")

    def __repr__(self):
        return f"<QueryFeedback id={self.id} query_id={self.query_id} type={self.feedback_type}>"


class QueryTemplate(Base):
    """
    Query templates for saved queries.

    Allows users to save and reuse common queries.
    """
    __tablename__ = "query_templates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    space_id = Column(Integer, ForeignKey("knowledge_spaces.id", ondelete="CASCADE"), nullable=True, index=True)

    # Template details
    name = Column(String(255), nullable=False)
    template_text = Column(Text, nullable=False)  # Query template with parameters
    parameters = Column(JSON, nullable=True)  # Template parameters: {"param1": "default_value"}

    # Usage statistics
    usage_count = Column(Integer, default=0, nullable=False)
    success_rate = Column(Float, default=0.0, nullable=False)  # Average feedback score

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    space = relationship("KnowledgeSpace", backref="query_templates")

    def __repr__(self):
        return f"<QueryTemplate id={self.id} name={self.name} usage={self.usage_count}>"


class DocumentRelationship(Base):
    """
    Relationships between documents.

    Supports document linking, references, citations, and cross-document retrieval.
    """
    __tablename__ = "document_relationships"

    id = Column(Integer, primary_key=True, index=True)
    source_document_id = Column(
        Integer,
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    target_document_id = Column(
        Integer,
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Relationship type
    relationship_type = Column(
        String(50),
        nullable=False,
        index=True
    )  # 'reference', 'citation', 'related', 'parent', 'child', 'similar'

    # Relationship metadata
    context = Column(Text, nullable=True)  # Context where relationship was found
    confidence = Column(Float, nullable=True)  # Confidence score (0-1) for auto-detected relationships

    # Creator
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    source_document = relationship(
        "KnowledgeDocument",
        foreign_keys=[source_document_id],
        backref="outgoing_relationships"
    )
    target_document = relationship(
        "KnowledgeDocument",
        foreign_keys=[target_document_id],
        backref="incoming_relationships"
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            'source_document_id',
            'target_document_id',
            'relationship_type',
            name='uq_document_relationship'
        ),
        Index(
            'ix_document_relationships_source_target',
            'source_document_id',
            'target_document_id'
        ),
    )

    def __repr__(self):
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

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    space_id = Column(Integer, ForeignKey("knowledge_spaces.id", ondelete="CASCADE"), nullable=True, index=True)

    # Dataset details
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Queries with expected results (JSON)
    # Format: [{"query": "...", "expected_chunk_ids": [1, 2, 3], "relevance_scores": [1.0, 0.8, 0.6]}]
    queries = Column(JSON, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    space = relationship("KnowledgeSpace", backref="evaluation_datasets")
    results = relationship("EvaluationResult", back_populates="dataset", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<EvaluationDataset id={self.id} name={self.name} queries={len(self.queries) if self.queries else 0}>"


class EvaluationResult(Base):
    """
    Evaluation result for a query in a dataset.

    Stores quality metrics for retrieval evaluation.
    """
    __tablename__ = "evaluation_results"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    query_id = Column(Integer, ForeignKey("knowledge_queries.id", ondelete="SET NULL"), nullable=True, index=True)

    # Quality metrics (JSON)
    # Format: {"precision": 0.8, "recall": 0.6, "mrr": 0.75, "ndcg": 0.82}
    metrics = Column(JSON, nullable=False)

    # Retrieval method used
    method = Column(String(50), nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    dataset = relationship("EvaluationDataset", back_populates="results")
    query = relationship("KnowledgeQuery", backref="evaluation_results")

    def __repr__(self):
        return f"<EvaluationResult id={self.id} dataset_id={self.dataset_id} method={self.method}>"


class ChunkTestResult(Base):
    """
    Chunk test result for comparing chunking methods.

    Stores results from RAG chunk testing comparing semchunk vs mindchunk.
    Uses UUID for session_id to enable secure, non-guessable session tracking.
    """
    __tablename__ = "chunk_test_results"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(36), nullable=True, index=True, default=generate_uuid)  # UUID for session tracking
    dataset_name = Column(String(100), nullable=False, index=True)  # 'FinanceBench', 'user_documents', etc.
    document_ids = Column(JSON, nullable=True)  # List of document IDs tested (for user documents)

    # Chunking comparison
    semchunk_chunk_count = Column(Integer, nullable=False, default=0)
    mindchunk_chunk_count = Column(Integer, nullable=False, default=0)
    chunk_stats = Column(JSON, nullable=True)  # Detailed chunk statistics

    # Retrieval comparison
    retrieval_metrics = Column(JSON, nullable=True)  # {semchunk: {...}, mindchunk: {...}}
    comparison_summary = Column(JSON, nullable=True)  # Winner, differences, recommendations

    # Evaluation results
    evaluation_results = Column(JSON, nullable=True)  # Comprehensive metrics organized by dimension

    # Progress tracking
    status = Column(
        Enum('pending', 'processing', 'completed', 'failed', name='chunk_test_status'),
        default='pending',
        nullable=False,
        index=True
    )
    current_method = Column(String(50), nullable=True)  # Currently processing chunking method
    # Current stage: 'chunking', 'retrieval', 'evaluation', 'completed'
    current_stage = Column(String(50), nullable=True)
    progress_percent = Column(Integer, default=0, nullable=False)  # Overall progress (0-100)
    completed_methods = Column(JSON, nullable=True)  # List of completed methods: ['spacy', 'semchunk', ...]

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", backref="chunk_test_results")

    @property
    def processing_progress(self) -> Optional[str]:
        """
        Get standardized progress string format compatible with ChunkTestDocument.
        
        Returns:
            Progress string in format "stage (method)" or "stage"
        """
        if not self.current_stage:
            return None

        if self.current_method:
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

    def __repr__(self):
        return f"<ChunkTestResult id={self.id} user_id={self.user_id} dataset_name={self.dataset_name}>"


class ChunkTestDocument(Base):
    """
    Document uploaded specifically for chunk testing.

    Separate from KnowledgeDocument - these are temporary test documents
    that don't interfere with the user's knowledge space.
    Max 5 documents per user for testing purposes.
    """
    __tablename__ = "chunk_test_documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # Storage path
    file_type = Column(String(100), nullable=False)  # MIME type
    file_size = Column(Integer, nullable=False)  # Bytes

    # Processing status
    status = Column(
        Enum('pending', 'processing', 'completed', 'failed', name='chunk_test_document_status'),
        default='pending',
        nullable=False,
        index=True
    )
    error_message = Column(Text, nullable=True)  # Error details if failed
    processing_task_id = Column(String(255), nullable=True)  # Celery task ID
    # Current processing stage: 'extracting', 'cleaning', 'chunking', 'embedding', 'indexing'
    processing_progress = Column(String(50), nullable=True)
    processing_progress_percent = Column(Integer, default=0, nullable=False)  # Progress percentage 0-100

    # Processing results
    chunk_count = Column(Integer, default=0, nullable=False)
    meta_data = Column(JSON, nullable=True)  # Store processing results and metadata

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="chunk_test_documents")
    chunks = relationship("ChunkTestDocumentChunk", back_populates="document", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name='chk_chunk_test_document_status'
        ),
        Index('ix_chunk_test_documents_user_id_status', 'user_id', 'status'),
    )

    @property
    def progress_percent(self) -> int:
        """
        Get progress percentage (alias for processing_progress_percent for consistency).
        
        Returns:
            Progress percentage (0-100)
        """
        return self.processing_progress_percent

    def __repr__(self):
        return f"<ChunkTestDocument id={self.id} file_name={self.file_name} status={self.status}>"


class ChunkTestDocumentChunk(Base):
    """
    Text chunk from a chunk test document.

    Separate from DocumentChunk - these chunks are only used for testing.
    """
    __tablename__ = "chunk_test_document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("chunk_test_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)  # Order within document
    text = Column(Text, nullable=False)  # Chunk content

    # Position in original document
    start_char = Column(Integer, nullable=False)
    end_char = Column(Integer, nullable=False)

    # Chunking method used (spacy, semchunk, chonkie, langchain, mindchunk)
    chunking_method = Column(String(50), nullable=True, index=True)

    # Additional metadata
    meta_data = Column(JSON, nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    document = relationship("ChunkTestDocument", back_populates="chunks")

    # Indexes for efficient queries
    __table_args__ = (
        Index('ix_chunk_test_document_chunks_document_id_chunk_index', 'document_id', 'chunk_index'),
        Index('ix_chunk_test_document_chunks_chunking_method', 'chunking_method'),
        Index('ix_chunk_test_document_chunks_document_method', 'document_id', 'chunking_method'),
    )

    def __repr__(self):
        return f"<ChunkTestDocumentChunk id={self.id} document_id={self.document_id} chunk_index={self.chunk_index}>"
