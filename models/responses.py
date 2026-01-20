"""
Response Models
===============

Pydantic models for API response validation and documentation.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str = Field(..., description="Error message")
    error_type: Optional[str] = Field(None, description="Type of error")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional error context")
    timestamp: Optional[float] = Field(None, description="Error timestamp")

    class Config:
        """Configuration for ErrorResponse JSON schema"""
        json_schema_extra = {
            "example": {
                "error": "Invalid diagram type",
                "error_type": "validation",
                "timestamp": 1696800000.0
            }
        }


class GenerateResponse(BaseModel):
    """Response model for /api/generate endpoint"""
    success: bool = Field(..., description="Whether generation succeeded")
    spec: Optional[Dict[str, Any]] = Field(None, description="Generated diagram specification")
    diagram_type: Optional[str] = Field(None, description="Detected/used diagram type")
    language: Optional[str] = Field(None, description="Language used")
    is_learning_sheet: Optional[bool] = Field(False, description="Whether this is a learning sheet")
    hidden_node_percentage: Optional[float] = Field(0.0, description="Percentage of nodes hidden for learning")
    error: Optional[str] = Field(None, description="Error message if failed")
    warning: Optional[str] = Field(None, description="Warning message if partial recovery occurred")
    recovery_warnings: Optional[List[str]] = Field(None, description="Detailed recovery warnings")
    use_default_template: Optional[bool] = Field(
        False,
        description="Whether to use default template (prompt-based generation)"
    )
    extracted_topic: Optional[str] = Field(None, description="Extracted topic from prompt")

    class Config:
        """Configuration for GenerateResponse JSON schema"""
        json_schema_extra = {
            "example": {
                "success": True,
                "spec": {"topic": "Photosynthesis", "concepts": []},
                "diagram_type": "concept_map",
                "language": "zh"
            }
        }


class HealthResponse(BaseModel):
    """Response model for /health endpoint"""
    status: str = Field(..., description="Health status")
    version: str = Field(..., description="Application version")

    class Config:
        """Configuration for HealthResponse JSON schema"""
        json_schema_extra = {
            "example": {
                "status": "ok",
                "version": "4.9.0"  # Example only - actual version from config.VERSION
            }
        }


class StatusResponse(BaseModel):
    """Response model for status endpoint"""
    status: str = Field(..., description="Status message")
    timestamp: Optional[float] = Field(None, description="Response timestamp")


# ============================================================================
# HEALTH CHECK RESPONSE MODELS
# ============================================================================

class ModelHealthStatus(BaseModel):
    """Health status for a single LLM model"""
    status: str = Field(..., description="Health status: healthy or unhealthy")
    latency: Optional[float] = Field(None, description="Response latency in seconds")
    error: Optional[str] = Field(None, description="Error message if unhealthy")
    error_type: Optional[str] = Field(None, description="Type of error (connection_error, timeout, etc.)")
    note: Optional[str] = Field(None, description="Additional notes about the service")


class LLMHealthResponse(BaseModel):
    """Response model for LLM health check endpoint"""
    status: str = Field(..., description="Overall status: success or error")
    health: Dict[str, Any] = Field(..., description="Health data for all models")
    circuit_states: Dict[str, str] = Field(..., description="Circuit breaker states for each model")
    timestamp: int = Field(..., description="Unix timestamp of health check")
    degraded: Optional[bool] = Field(None, description="True if some models are unhealthy")
    unhealthy_count: Optional[int] = Field(None, description="Number of unhealthy models")
    healthy_count: Optional[int] = Field(None, description="Number of healthy models")
    total_models: Optional[int] = Field(None, description="Total number of models checked")

    class Config:
        """Configuration for LLMHealthResponse JSON schema"""
        json_schema_extra = {
            "example": {
                "status": "success",
                "health": {
                    "available_models": ["qwen", "qwen-turbo"],
                    "qwen": {"status": "healthy", "latency": 0.8},
                    "qwen-turbo": {"status": "healthy", "latency": 0.34}
                },
                "circuit_states": {
                    "qwen": "closed",
                    "qwen-turbo": "closed"
                },
                "timestamp": 1642012345,
                "degraded": False,
                "unhealthy_count": 0,
                "healthy_count": 2,
                "total_models": 2
            }
        }


class DatabaseHealthResponse(BaseModel):
    """Response model for database health check endpoint"""
    status: str = Field(..., description="Health status: healthy or unhealthy")
    database_healthy: bool = Field(..., description="Whether database integrity check passed")
    database_message: str = Field(..., description="Health check message")
    database_stats: Dict[str, Any] = Field(default_factory=dict, description="Database statistics")
    timestamp: int = Field(..., description="Unix timestamp of health check")

    class Config:
        """Configuration for DatabaseHealthResponse JSON schema"""
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "database_healthy": True,
                "database_message": "Database integrity check passed",
                "database_stats": {
                    "path": "data/mindgraph.db",
                    "size_mb": 2.5,
                    "total_rows": 650
                },
                "timestamp": 1642012345
            }
        }


# ============================================================================
# TAB MODE RESPONSE MODELS
# ============================================================================

class TabSuggestionItem(BaseModel):
    """Individual suggestion item"""
    text: str = Field(..., description="Suggestion text")
    confidence: float = Field(0.9, ge=0.0, le=1.0, description="Confidence score")


class TabSuggestionResponse(BaseModel):
    """Response model for /api/tab_suggestions endpoint"""
    success: bool = Field(..., description="Whether request succeeded")
    mode: str = Field("autocomplete", description="Mode: 'autocomplete'")
    suggestions: List[TabSuggestionItem] = Field(default_factory=list, description="List of suggestions")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    error: Optional[str] = Field(None, description="Error message if failed")

    class Config:
        """Configuration for TabSuggestionResponse JSON schema"""
        json_schema_extra = {
            "example": {
                "success": True,
                "mode": "autocomplete",
                "suggestions": [
                    {"text": "fruit", "confidence": 0.9},
                    {"text": "fruit juice", "confidence": 0.8}
                ],
                "request_id": "tab_1234567890"
            }
        }


class TabExpandChild(BaseModel):
    """Child node for expansion"""
    text: str = Field(..., description="Child node text")
    id: str = Field(..., description="Child node ID")


class TabExpandResponse(BaseModel):
    """Response model for /api/tab_expand endpoint"""
    success: bool = Field(..., description="Whether expansion succeeded")
    mode: str = Field("expansion", description="Mode: 'expansion'")
    children: List[TabExpandChild] = Field(default_factory=list, description="Generated child nodes")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    error: Optional[str] = Field(None, description="Error message if failed")

    class Config:
        """Configuration for TabExpandResponse JSON schema"""
        json_schema_extra = {
            "example": {
                "success": True,
                "mode": "expansion",
                "children": [
                    {"text": "Group Discussions", "id": "child_0"},
                    {"text": "Role Playing", "id": "child_1"},
                    {"text": "Case Studies", "id": "child_2"}
                ],
                "request_id": "tab_expand_1234567890"
            }
        }


# ============================================================================
# DIAGRAM STORAGE RESPONSE MODELS
# ============================================================================

class DiagramResponse(BaseModel):
    """Response model for a single diagram"""
    id: str = Field(..., description="Diagram UUID")
    title: str = Field(..., description="Diagram title")
    diagram_type: str = Field(..., description="Type of diagram")
    spec: Dict[str, Any] = Field(..., description="Diagram specification")
    language: str = Field(..., description="Language code")
    thumbnail: Optional[str] = Field(None, description="Base64 encoded thumbnail")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        """Configuration for DiagramResponse JSON schema"""
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "My Mind Map",
                "diagram_type": "mind_map",
                "spec": {"topic": "Central Topic", "children": []},
                "language": "zh",
                "thumbnail": None,
                "created_at": "2026-01-07T12:00:00",
                "updated_at": "2026-01-07T12:00:00"
            }
        }


class DiagramListItem(BaseModel):
    """List item for diagram gallery view"""
    id: str = Field(..., description="Diagram UUID")
    title: str = Field(..., description="Diagram title")
    diagram_type: str = Field(..., description="Type of diagram")
    thumbnail: Optional[str] = Field(None, description="Base64 encoded thumbnail")
    updated_at: datetime = Field(..., description="Last update timestamp")
    is_pinned: bool = Field(False, description="Whether diagram is pinned to top")

    class Config:
        """Configuration for DiagramListItem JSON schema"""
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "My Mind Map",
                "diagram_type": "mind_map",
                "thumbnail": None,
                "updated_at": "2026-01-07T12:00:00",
                "is_pinned": False
            }
        }


class DiagramListResponse(BaseModel):
    """Response model for diagram list with pagination"""
    diagrams: List[DiagramListItem] = Field(default_factory=list, description="List of diagrams")
    total: int = Field(..., description="Total number of diagrams")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    has_more: bool = Field(..., description="Whether there are more pages")
    max_diagrams: int = Field(20, description="Maximum diagrams allowed per user")

    class Config:
        """Configuration for DiagramListResponse JSON schema"""
        json_schema_extra = {
            "example": {
                "diagrams": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "title": "My Mind Map",
                        "diagram_type": "mind_map",
                        "thumbnail": None,
                        "updated_at": "2026-01-07T12:00:00"
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 10,
                "has_more": False,
                "max_diagrams": 20
            }
        }


# ============================================================================
# KNOWLEDGE SPACE RESPONSE MODELS
# ============================================================================

class DocumentResponse(BaseModel):
    """Response model for a single document."""

    id: int
    file_name: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int
    error_message: Optional[str] = None
    processing_progress: Optional[str] = None
    processing_progress_percent: int = 0
    created_at: str
    updated_at: str


class DocumentListResponse(BaseModel):
    """Response model for a list of documents."""

    documents: List[DocumentResponse]
    total: int


class RetrievalTestResult(BaseModel):
    """Response model for a single retrieval test result."""

    chunk_id: int
    text: str
    score: float
    document_id: int
    document_name: str
    chunk_index: int


class RetrievalTestResponse(BaseModel):
    """Response model for retrieval test results."""

    query: str
    method: str
    results: List[RetrievalTestResult]
    timing: dict
    stats: dict


class RetrievalTestHistoryItem(BaseModel):
    """Response model for a single retrieval test history item."""

    id: int
    query: str
    method: str
    top_k: int
    score_threshold: float
    result_count: int
    timing: dict
    created_at: str


class RetrievalTestHistoryResponse(BaseModel):
    """Response model for retrieval test history."""

    queries: List[RetrievalTestHistoryItem]
    total: int


class CompressionMetricsResponse(BaseModel):
    """Response model for compression metrics."""

    compression_enabled: bool
    compression_type: Optional[str]
    points_count: int
    vector_size: int
    estimated_uncompressed_size: float
    estimated_compressed_size: float
    compression_ratio: float
    storage_savings_percent: float
    error: Optional[str] = None


class BatchResponse(BaseModel):
    """Response model for batch upload operations."""

    batch_id: int
    status: str
    total_count: int
    completed_count: int
    failed_count: int
    created_at: str
    updated_at: str


class VersionResponse(BaseModel):
    """Response model for a document version."""

    id: int
    document_id: int
    version_number: int
    chunk_count: int
    change_summary: Optional[Dict[str, Any]] = None
    created_at: str


class VersionListResponse(BaseModel):
    """Response model for a list of document versions."""

    versions: List[VersionResponse]
    total: int


class QueryTemplateResponse(BaseModel):
    """Response model for a query template."""

    id: int
    name: str
    template_text: str
    parameters: Optional[Dict[str, Any]] = None
    usage_count: int
    success_rate: float
    created_at: str
    updated_at: str


class QueryAnalyticsResponse(BaseModel):
    """Response model for query analytics."""

    common_queries: List[Dict[str, Any]]
    low_performing_queries: List[Dict[str, Any]]
    average_scores: Dict[str, float]
    suggestions: List[str]


class RelationshipResponse(BaseModel):
    """Response model for a document relationship."""

    id: int
    source_document_id: int
    target_document_id: int
    relationship_type: str
    context: Optional[str] = None
    created_at: str


class EvaluationDatasetResponse(BaseModel):
    """Response model for an evaluation dataset."""

    id: int
    name: str
    description: Optional[str] = None
    queries: List[Dict[str, Any]]
    created_at: str
    updated_at: str


class EvaluationRunResponse(BaseModel):
    """Response model for evaluation run results."""

    dataset_id: int
    method: str
    total_queries: int
    evaluated_queries: int
    average_metrics: Dict[str, float]
    query_results: List[Dict[str, Any]]


class ChunkTestProgressResponse(BaseModel):
    """Response model for chunk test progress."""

    test_id: int
    session_id: Optional[str] = None  # UUID for session tracking
    status: str  # 'pending', 'processing', 'completed', 'failed'
    current_method: Optional[str] = None
    current_stage: Optional[str] = None
    progress_percent: int = 0
    completed_methods: Optional[List[str]] = None


class ChunkTestResultResponse(BaseModel):
    """Response model for chunk test results."""

    test_id: int
    session_id: Optional[str] = None  # UUID for session tracking
    dataset_name: str
    document_ids: Optional[List[int]] = None
    chunking_comparison: Dict[str, Any]
    retrieval_comparison: Dict[str, Any]
    summary: Dict[str, Any]
    evaluation_results: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    current_method: Optional[str] = None
    current_stage: Optional[str] = None
    progress_percent: Optional[int] = None
    completed_methods: Optional[List[str]] = None
    created_at: str
