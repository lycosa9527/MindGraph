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

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class RetrievalTestRequest(BaseModel):
    """Request model for testing retrieval functionality."""

    query: str = Field(..., max_length=250)
    method: str = Field(default="hybrid", pattern="^(semantic|keyword|hybrid)$")
    top_k: int = Field(default=5, ge=1, le=10)
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0)


class MetadataUpdateRequest(BaseModel):
    """Request model for updating document metadata."""

    tags: Optional[List[str]] = None
    category: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    custom_fields: Optional[Dict[str, Any]] = None


class ProcessSelectedRequest(BaseModel):
    """Request model for processing selected documents."""

    document_ids: List[int] = Field(..., min_length=1)


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
    relationship_type: str = Field(
        ...,
        pattern="^(reference|citation|related|parent|child|similar)$"
    )
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
        description="Chunking modes to compare: 'spacy', 'semchunk', 'chonkie', 'langchain', 'mindchunk', 'qa'"
    )


class ChunkTestUserDocumentsRequest(BaseModel):
    """Request model for testing chunking methods with user documents."""

    document_ids: List[int] = Field(..., min_length=1)
    queries: List[str] = Field(..., min_length=1)
    modes: Optional[List[str]] = Field(
        default=["spacy", "semchunk", "chonkie", "langchain", "mindchunk"],
        description="Chunking modes to compare: 'spacy', 'semchunk', 'chonkie', 'langchain', 'mindchunk', 'qa'"
    )


class ManualEvaluationRequest(BaseModel):
    """Request model for manual chunk evaluation."""

    query: str = Field(..., min_length=1, max_length=500)
    method: str = Field(..., description="Chunking method to evaluate")
    chunk_ids: Optional[List[int]] = None
    answer: Optional[str] = None
    model: str = Field(default="qwen-max", description="DashScope model to use")
