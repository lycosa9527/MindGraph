"""
Knowledge Space Request Models
==============================

Pydantic models for Knowledge Space API request validation.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Literal, Optional, Dict, Any, List
from pydantic import BaseModel, Field, model_validator

ChatHandoffPlatform = Literal["wechat", "dingtalk", "wecom"]


class RetrievalTestRequest(BaseModel):
    """Request model for testing retrieval functionality."""

    query: str = Field(..., max_length=250)
    method: Optional[str] = Field(default=None, pattern="^(semantic|keyword|hybrid)$")
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    score_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class KnowledgeSpaceSettingsUpdateRequest(BaseModel):
    """Request model for updating user Knowledge Space preferences."""

    default_method: str = Field(default="hybrid", pattern="^(semantic|keyword|hybrid)$")
    top_k: int = Field(default=5, ge=1, le=20)
    score_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    chunk_size: int = Field(default=500, ge=100, le=2000)
    chunk_overlap: int = Field(default=50, ge=0, le=200)


class MetadataUpdateRequest(BaseModel):
    """Request model for updating document metadata."""

    tags: Optional[List[str]] = None
    category: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    custom_fields: Optional[Dict[str, Any]] = None


class ProcessSelectedRequest(BaseModel):
    """Request model for processing selected documents."""

    document_ids: List[int] = Field(..., min_length=1)


class PackageCreateRequest(BaseModel):
    """Request model for creating a File Center package."""

    name: str = Field(..., min_length=1, max_length=200)
    diagram_id: Optional[str] = Field(default=None, max_length=36)
    source: str = Field(default="canvas", pattern="^(canvas|knowledge_space|chrome_extension|doc_summary)$")


class PackageUpdateRequest(BaseModel):
    """Request model for renaming or relinking a package."""

    name: Optional[str] = Field(default=None, max_length=200)
    diagram_id: Optional[str] = Field(default=None, max_length=36)


class PackageIngestTextRequest(BaseModel):
    """Request model for ingesting pasted text into a package."""

    content: str = Field(..., min_length=1, max_length=200000)
    title: Optional[str] = Field(default=None, max_length=200)
    language: Optional[str] = Field(default=None, max_length=10)


class PackageIngestWebRequest(BaseModel):
    """Request model for ingesting a web content snapshot into a package."""

    page_content: str = Field(..., min_length=1, max_length=200000)
    page_url: Optional[str] = Field(default=None, max_length=2000)
    page_title: Optional[str] = Field(default=None, max_length=300)
    language: Optional[str] = Field(default=None, max_length=10)


class PackageIngestWebUrlRequest(BaseModel):
    """Fetch a public URL server-side and ingest as a web snapshot."""

    page_url: str = Field(..., min_length=1, max_length=2000)
    language: Optional[str] = Field(default=None, max_length=10)


class DocSummarySessionStartRequest(BaseModel):
    """Start or resume a Document Summary session package."""

    diagram_id: Optional[str] = Field(default=None, max_length=36)
    diagram_title: Optional[str] = Field(default=None, max_length=200)
    package_id: Optional[int] = Field(default=None, ge=1)
    create_if_missing: bool = Field(
        default=False,
        description="When true, create a package if none is linked to the session yet.",
    )


class ChatHandoffStartRequest(BaseModel):
    """Mint a pairing code for file-reader ingest."""

    package_id: int = Field(..., ge=1)


class ChatHandoffIngestRequest(BaseModel):
    """Ingest chat transcript via pairing code (file-reader client)."""

    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    platform: ChatHandoffPlatform
    chat_title: str = Field(..., min_length=1, max_length=200)
    content: Optional[str] = Field(default=None, max_length=200000)
    messages: Optional[List[Dict[str, Any]]] = Field(default=None, max_length=5000)
    source_export_name: Optional[str] = Field(default=None, max_length=255)
    language: Optional[str] = Field(default=None, max_length=10)

    @model_validator(mode="after")
    def require_content_or_messages(self) -> "ChatHandoffIngestRequest":
        """Require at least one of ``content`` or ``messages``."""
        has_messages = bool(self.messages)
        has_content = bool((self.content or "").strip())
        if not has_messages and not has_content:
            raise ValueError("Either content or messages is required")
        return self


class QueryFeedbackRequest(BaseModel):
    """Request model for submitting query feedback."""

    feedback_type: str = Field(..., pattern="^(positive|negative|neutral)$")
    feedback_score: Optional[int] = Field(None, ge=1, le=5)
    relevant_chunk_ids: Optional[List[int]] = None
    irrelevant_chunk_ids: Optional[List[int]] = None


class QueryTemplateRequest(BaseModel):
    """Request model for creating a query template."""

    name: str = Field(..., max_length=255)
    template_text: str
    parameters: Optional[Dict[str, Any]] = None


class RelationshipRequest(BaseModel):
    """Request model for creating a document relationship."""

    target_document_id: int
    relationship_type: str = Field(..., pattern="^(reference|citation|related|parent|child|similar)$")
    context: Optional[str] = None


class EvaluationDatasetRequest(BaseModel):
    """Request model for creating an evaluation dataset."""

    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    queries: List[Dict[str, Any]]


class EvaluationRunRequest(BaseModel):
    """Request model for running an evaluation."""

    dataset_id: int
    method: str = Field(default="hybrid", pattern="^(semantic|keyword|hybrid)$")


class RollbackRequest(BaseModel):
    """Request model for rolling back a document to a previous version."""

    version_number: int


class ChunkTestBenchmarkRequest(BaseModel):
    """Request model for testing chunking methods with benchmark dataset."""

    dataset_name: str = Field(..., pattern="^(FinanceBench|KG-RAG|FRAMES|PubMedQA)$")
    queries: Optional[List[str]] = None  # Optional custom queries
    modes: Optional[List[str]] = Field(
        default=["spacy", "semchunk", "chonkie", "langchain", "mindchunk"],
        description="Chunking modes to compare: 'spacy', 'semchunk', 'chonkie', 'langchain', 'mindchunk', 'qa'",
    )


class ChunkTestUserDocumentsRequest(BaseModel):
    """Request model for testing chunking methods with user documents."""

    document_ids: List[int] = Field(..., min_length=1)
    queries: List[str] = Field(..., min_length=1)
    modes: Optional[List[str]] = Field(
        default=["spacy", "semchunk", "chonkie", "langchain", "mindchunk"],
        description="Chunking modes to compare: 'spacy', 'semchunk', 'chonkie', 'langchain', 'mindchunk', 'qa'",
    )


class ManualEvaluationRequest(BaseModel):
    """Request model for manual chunk evaluation."""

    query: str = Field(..., min_length=1, max_length=500)
    method: str = Field(..., description="Chunking method to evaluate")
    chunk_ids: Optional[List[int]] = None
    answer: Optional[str] = None
    model: str = Field(default="qwen-max", description="DashScope model to use")
