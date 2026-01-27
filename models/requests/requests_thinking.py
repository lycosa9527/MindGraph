"""Thinking Mode Request Models.

Pydantic models for validating Node Palette and Tab Mode API requests.

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
        description="Mode for double bubble map: 'similarities' or 'differences'"
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
        description="Mode for double bubble map: 'similarities' or 'differences'"
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


# ============================================================================
# TAB MODE REQUEST MODELS
# ============================================================================

class TabSuggestionRequest(BaseModel):
    """Request model for /api/tab_suggestions endpoint (editing autocomplete)"""
    mode: str = Field(
        "autocomplete",
        description="Mode: 'autocomplete' for editing suggestions"
    )
    diagram_type: DiagramType = Field(..., description="Type of diagram")
    main_topics: List[str] = Field(
        ..., min_items=1, description="Main topic nodes"
    )
    node_category: Optional[str] = Field(
        None, description="Node category"
    )
    partial_input: str = Field(
        ..., description="User's current partial input"
    )
    existing_nodes: Optional[List[str]] = Field(
        None, description="Existing nodes in same category"
    )
    language: Language = Field(Language.EN, description="Language code")
    llm: LLMModel = Field(LLMModel.QWEN, description="LLM model to use")
    cursor_position: Optional[int] = Field(
        None, description="Cursor position in input"
    )
    page_offset: int = Field(
        0, ge=0, description="Page offset for pagination (0 = first page)"
    )

    @field_validator('diagram_type', mode='before')
    @classmethod
    def normalize_diagram_type(cls, v):
        """Normalize diagram type aliases (e.g., 'mindmap' -> 'mind_map')"""
        if v is None:
            return v

        # Convert to string if it's already an enum
        v_str = v.value if hasattr(v, 'value') else str(v)

        # Normalize known aliases
        aliases = {
            'mindmap': 'mind_map',
        }

        normalized = aliases.get(v_str, v_str)

        # Return normalized string (Pydantic will convert to enum)
        return normalized

    class Config:
        """Configuration for TabSuggestionRequest model."""

        json_schema_extra = {
            "example": {
                "mode": "autocomplete",
                "diagram_type": "double_bubble_map",
                "main_topics": ["apples", "oranges"],
                "node_category": "similarities",
                "partial_input": "fru",
                "existing_nodes": ["vitamin C"],
                "language": "en",
                "llm": "qwen"
            }
        }


class TabExpandRequest(BaseModel):
    """Request model for /api/tab_expand endpoint (viewing node expansion)"""
    mode: str = Field(
        "expansion", description="Mode: 'expansion' for node expansion"
    )
    diagram_type: DiagramType = Field(..., description="Type of diagram")
    node_id: str = Field(..., description="Node ID to expand")
    node_text: str = Field(..., description="Text of the node to expand")
    node_type: str = Field(
        "branch", description="Type of node (branch, category, step, part)"
    )
    main_topic: Optional[str] = Field(
        None, description="Main topic/center node text"
    )
    existing_children: Optional[List[str]] = Field(
        None, description="Existing children nodes"
    )
    num_children: int = Field(
        4, ge=1, le=10, description="Number of children to generate"
    )
    language: Language = Field(Language.EN, description="Language code")
    llm: LLMModel = Field(LLMModel.QWEN, description="LLM model to use")
    session_id: Optional[str] = Field(
        None, description="Session ID for tracking"
    )

    @field_validator('diagram_type', mode='before')
    @classmethod
    def normalize_diagram_type(cls, v):
        """Normalize diagram type aliases (e.g., 'mindmap' -> 'mind_map')"""
        if v is None:
            return v

        # Convert to string if it's already an enum
        v_str = v.value if hasattr(v, 'value') else str(v)

        # Normalize known aliases
        aliases = {
            'mindmap': 'mind_map',
        }

        normalized = aliases.get(v_str, v_str)

        # Return normalized string (Pydantic will convert to enum)
        return normalized

    class Config:
        """Configuration for TabExpandRequest model."""

        json_schema_extra = {
            "example": {
                "mode": "expansion",
                "diagram_type": "mindmap",
                "node_id": "branch_0",
                "node_text": "Active Learning",
                "node_type": "branch",
                "main_topic": "Learning Methods",
                "existing_children": [],
                "num_children": 4,
                "language": "en",
                "llm": "qwen"
            }
        }
