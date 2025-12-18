"""
Response Models
===============

Pydantic models for API response validation and documentation.

Author: lycosa9527
Made by: MindSpring Team
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str = Field(..., description="Error message")
    error_type: Optional[str] = Field(None, description="Type of error")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional error context")
    timestamp: Optional[float] = Field(None, description="Error timestamp")
    
    class Config:
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
    use_default_template: Optional[bool] = Field(False, description="Whether to use default template (prompt-based generation)")
    extracted_topic: Optional[str] = Field(None, description="Extracted topic from prompt")
    
    class Config:
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

