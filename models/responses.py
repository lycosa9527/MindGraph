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
    """Response model for /status endpoint"""
    status: str = Field(..., description="Application status")
    framework: str = Field(..., description="Framework name")
    version: str = Field(..., description="Application version")
    uptime_seconds: float = Field(..., description="Uptime in seconds")
    memory_percent: float = Field(..., description="Memory usage percentage")
    timestamp: float = Field(..., description="Current timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "running",
                "framework": "FastAPI",
                "version": "4.9.0",  # Example only - actual version from config.VERSION
                "uptime_seconds": 3600.0,
                "memory_percent": 45.2,
                "timestamp": 1696800000.0
            }
        }

