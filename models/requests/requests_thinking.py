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

from utils.prompt_output_languages import is_prompt_output_language


def _validate_node_palette_language(value: str) -> str:
    """Generation language code (prompt-output registry)."""
    if not isinstance(value, str) or not value.strip():
        return 'en'
    lowered = value.strip().lower()
    if not is_prompt_output_language(lowered):
        raise ValueError("Language must be a supported generation language code")
    return lowered


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
    language: str = Field(
        'en',
        description="Prompt / generation language code (see prompt output registry)",
    )
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

    @field_validator('language')
    @classmethod
    def validate_start_language(cls, value: str) -> str:
        """Reject unknown generation language codes."""
        return _validate_node_palette_language(value)

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
    diagram_data: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Optional diagram snapshot; concept_map sends focus_question and root_concept "
            "for palette prompts"
        ),
    )
    educational_context: Optional[Dict[str, Any]] = Field(
        None, description="Educational context"
    )
    language: str = Field(
        'en',
        description="Prompt / generation language code (see prompt output registry)",
    )
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

    @field_validator('language')
    @classmethod
    def validate_next_language(cls, value: str) -> str:
        """Reject unknown generation language codes."""
        return _validate_node_palette_language(value)

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
        ..., min_length=0, description="List of selected node IDs"
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


class RelationshipLabelsStartRequest(BaseModel):
    """Request model for /thinking_mode/relationship_labels/start endpoint."""

    session_id: str = Field(
        ..., min_length=1, max_length=100,
        description="Relationship labels session ID (connectionId)"
    )
    concept_a: str = Field(..., description="Source concept text")
    concept_b: str = Field(..., description="Target concept text")
    topic: str = Field('', description="Concept map main topic")
    link_direction: Optional[str] = Field(
        None,
        description="Arrow direction: source_to_target, target_to_source, both, none"
    )
    language: str = Field(
        'en',
        description="Prompt / generation language code (see prompt output registry)",
    )

    @field_validator('language')
    @classmethod
    def validate_relationship_labels_start_language(cls, value: str) -> str:
        """Reject unknown generation language codes."""
        return _validate_node_palette_language(value)


class RelationshipLabelsCleanupRequest(BaseModel):
    """Request model for /thinking_mode/relationship_labels/cleanup endpoint."""

    connection_ids: List[str] = Field(
        default_factory=list,
        description="Connection IDs (session_ids) to clean up",
        max_length=100,
    )


class RelationshipLabelsNextRequest(BaseModel):
    """Request model for /thinking_mode/relationship_labels/next_batch endpoint."""

    session_id: str = Field(
        ..., min_length=1, max_length=100,
        description="Relationship labels session ID"
    )
    concept_a: str = Field(..., description="Source concept text")
    concept_b: str = Field(..., description="Target concept text")
    topic: str = Field('', description="Concept map main topic")
    link_direction: Optional[str] = Field(None, description="Arrow direction")
    language: str = Field(
        'en',
        description="Prompt / generation language code (see prompt output registry)",
    )

    @field_validator('language')
    @classmethod
    def validate_relationship_labels_next_language(cls, value: str) -> str:
        """Reject unknown generation language codes."""
        return _validate_node_palette_language(value)


class InlineRecommendationsStartRequest(BaseModel):
    """Request model for /thinking_mode/inline_recommendations/start endpoint."""

    session_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Session ID (typically node_id)",
    )
    diagram_type: str = Field(
        ...,
        description="Diagram type: mindmap, flow_map, tree_map, brace_map",
    )
    stage: str = Field(
        ...,
        description="Stage: branches, children, steps, substeps, categories, parts, subparts",
    )
    node_id: str = Field(
        ...,
        description="ID of the node being edited (for context)",
    )
    nodes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Current diagram nodes",
    )
    connections: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="Current diagram connections",
    )
    language: str = Field(
        'en',
        description="Prompt / generation language code (see prompt output registry)",
    )
    count: int = Field(15, ge=5, le=30, description="Recommendations to generate per LLM")
    models: Optional[List[str]] = Field(
        default=None,
        description="LLM models to use (e.g. ['qwen']). When set, only these models run.",
    )
    educational_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Educational context (raw_message, grade, subject) for prompt enrichment",
    )

    @field_validator('language')
    @classmethod
    def validate_inline_recommendations_start_language(cls, value: str) -> str:
        """Reject unknown generation language codes."""
        return _validate_node_palette_language(value)


class InlineRecommendationsNextRequest(BaseModel):
    """Request model for /thinking_mode/inline_recommendations/next_batch."""

    session_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Session ID",
    )
    diagram_type: str = Field(..., description="Diagram type")
    stage: str = Field(..., description="Stage")
    node_id: str = Field(..., description="Node ID")
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    connections: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    language: str = Field(
        'en',
        description="Prompt / generation language code (see prompt output registry)",
    )
    count: int = Field(15, ge=5, le=30, description="Recommendations per LLM")
    models: Optional[List[str]] = Field(
        default=None,
        description="LLM models to use (e.g. ['qwen']). When set, only these models run.",
    )
    educational_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Educational context for prompt enrichment",
    )

    @field_validator('language')
    @classmethod
    def validate_inline_recommendations_next_language(cls, value: str) -> str:
        """Reject unknown generation language codes."""
        return _validate_node_palette_language(value)


class InlineRecommendationsCleanupRequest(BaseModel):
    """Request model for /thinking_mode/inline_recommendations/cleanup."""

    node_ids: List[str] = Field(
        default_factory=list,
        description="Node IDs (session_ids) to clean up",
        max_length=100,
    )


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
