"""Thinking Mode Request Models.

Pydantic models for validating Node Palette API requests.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field, field_validator

from ..common import DiagramType, Language, LLMModel


# ============================================================================
# NODE PALETTE REQUEST MODELS
# ============================================================================

class NodePaletteStartRequest(BaseModel):
    """Request model for /thinking_mode/node_palette/start endpoint"""
    session_id: str = Field(
        ..., min_length=1, max_length=100,
        description="Node Palette session ID"
    )
    diagram_type: str = Field(
        ...,
        description=(
            "Diagram type ('circle_map', 'bubble_map', "
            "'double_bubble_map', 'tree_map', etc.)"
        )
    )
    diagram_data: Dict[str, Any] = Field(
        ..., description="Current diagram data"
    )
    educational_context: Optional[Dict[str, Any]] = Field(
        None, description="Educational context (grade level, subject, etc.)"
    )
    user_id: Optional[str] = Field(
        None, description="User identifier for analytics"
    )
    language: str = Field('en', description="UI language (en or zh)")
    mode: Optional[str] = Field(
        'similarities',
        description=(
            "Mode for double bubble map: 'similarities', 'differences', "
            "or 'both' (generates both concurrently)"
        )
    )
    # NEW: Stage-based generation for tree maps
    stage: Optional[str] = Field(
        'categories',
        description=(
            "Generation stage for tree maps: "
            "'dimensions', 'categories', or 'children'"
        )
    )
    stage_data: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Stage-specific data "
            "(e.g., {'dimension': 'Habitat', 'category_name': 'Water Animals'})"
        )
    )

    class Config:
        """Configuration for NodePaletteStartRequest model."""

        json_schema_extra = {
            "example": {
                "session_id": "palette_abc123",
                "diagram_type": "circle_map",
                "diagram_data": {
                    "center": {"text": "Photosynthesis"},
                    "children": [
                        {"id": "1", "text": "Sunlight"},
                        {"id": "2", "text": "Water"}
                    ]
                },
                "educational_context": {
                    "grade_level": "5th grade",
                    "subject": "Science",
                    "topic": "Plants"
                },
                "user_id": "user123"
            }
        }


class NodePaletteNextRequest(BaseModel):
    """Request model for /thinking_mode/node_palette/next_batch endpoint"""
    session_id: str = Field(
        ..., min_length=1, max_length=100,
        description="Node Palette session ID"
    )
    diagram_type: str = Field(
        ...,
        description=(
            "Diagram type ('circle_map', 'bubble_map', "
            "'double_bubble_map', 'tree_map', etc.)"
        )
    )
    center_topic: str = Field(
        ..., min_length=1, description="Center topic from diagram"
    )
    educational_context: Optional[Dict[str, Any]] = Field(
        None, description="Educational context"
    )
    language: str = Field('en', description="UI language (en or zh)")
    mode: Optional[str] = Field(
        'similarities',
        description=(
            "Mode for double bubble map: 'similarities', 'differences', "
            "or 'both' (generates both concurrently)"
        )
    )
    # NEW: Stage-based generation for tree maps
    stage: Optional[str] = Field(
        'categories',
        description=(
            "Generation stage for tree maps: "
            "'dimensions', 'categories', or 'children'"
        )
    )
    stage_data: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Stage-specific data "
            "(e.g., {'dimension': 'Habitat', 'category_name': 'Water Animals'})"
        )
    )

    class Config:
        """Configuration for NodePaletteNextRequest model."""

        json_schema_extra = {
            "example": {
                "session_id": "palette_abc123",
                "center_topic": "Photosynthesis",
                "educational_context": {
                    "grade_level": "5th grade",
                    "subject": "Science"
                }
            }
        }


class NodeSelectionRequest(BaseModel):
    """Request model for /thinking_mode/node_palette/select_node endpoint"""
    session_id: str = Field(
        ..., min_length=1, max_length=100,
        description="Node Palette session ID"
    )
    node_id: str = Field(
        ..., description="ID of the node being selected/deselected"
    )
    selected: bool = Field(
        ..., description="True if selected, False if deselected"
    )
    node_text: str = Field(
        ..., max_length=200, description="Text content of the node"
    )

    class Config:
        """Configuration for NodeSelectionRequest model."""

        json_schema_extra = {
            "example": {
                "session_id": "palette_abc123",
                "node_id": "palette_abc123_qwen_1_5",
                "selected": True,
                "node_text": "Chlorophyll pigments"
            }
        }


class NodePaletteFinishRequest(BaseModel):
    """Request model for /thinking_mode/node_palette/finish endpoint"""
    session_id: str = Field(
        ..., min_length=1, max_length=100,
        description="Node Palette session ID"
    )
    selected_node_ids: List[str] = Field(
        ..., min_items=0, description="List of selected node IDs"
    )
    total_nodes_generated: int = Field(
        ..., ge=0, description="Total number of nodes generated"
    )
    batches_loaded: int = Field(
        ..., ge=1, description="Number of batches loaded"
    )
    diagram_type: Optional[str] = Field(
        None, description="Diagram type for cleanup in generator"
    )

    class Config:
        """Configuration for NodePaletteFinishRequest model."""

        json_schema_extra = {
            "example": {
                "session_id": "palette_abc123",
                "selected_node_ids": [
                    "palette_abc123_qwen_1_5",
                    "palette_abc123_qwen_1_12",
                    "palette_abc123_hunyuan_2_3"
                ],
                "total_nodes_generated": 69,
                "batches_loaded": 4
            }
        }


class NodePaletteCleanupRequest(BaseModel):
    """Request model for /thinking_mode/node_palette/cleanup endpoint

    Simplified model for session cleanup - only requires session_id.
    Used when user leaves canvas or navigates away.
    """
    session_id: str = Field(
        ..., min_length=1, max_length=100,
        description="Node Palette session ID"
    )
    diagram_type: Optional[str] = Field(
        None, description="Diagram type for cleanup in generator"
    )

    class Config:
        """Configuration for NodePaletteCleanupRequest model."""

        json_schema_extra = {
            "example": {
                "session_id": "palette_abc123",
                "diagram_type": "circle_map"
            }
        }
