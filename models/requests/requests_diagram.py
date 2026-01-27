"""Diagram Generation and Storage Request Models.

Pydantic models for validating diagram generation, export, and storage API requests.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field, field_validator

from ..common import DiagramType, Language, LLMModel


class GenerateRequest(BaseModel):
    """Request model for /api/generate endpoint"""
    prompt: str = Field(
        ..., min_length=1, max_length=10000,
        description="User prompt for diagram generation"
    )
    diagram_type: Optional[DiagramType] = Field(
        None, description="Diagram type (auto-detected if not provided)"
    )
    language: Language = Field(
        Language.ZH, description="Language for diagram generation"
    )
    llm: LLMModel = Field(LLMModel.QWEN, description="LLM model to use")
    models: Optional[List[str]] = Field(
        None,
        description=(
            "List of models for parallel generation "
            "(e.g., ['qwen', 'deepseek', 'kimi', 'doubao'])"
        )
    )
    dimension_preference: Optional[str] = Field(
        None, description="Optional dimension preference for certain diagrams"
    )
    request_type: Optional[str] = Field(
        'diagram_generation',
        description=(
            "Request type for token tracking: "
            "'diagram_generation' or 'autocomplete'"
        )
    )
    use_rag: Optional[bool] = Field(
        False,
        description=(
            "Whether to use RAG (Knowledge Space) context "
            "for enhanced diagram generation"
        )
    )
    rag_top_k: Optional[int] = Field(
        5, ge=1, le=10,
        description="Number of RAG context chunks to retrieve (1-10)"
    )
    # Bridge map specific: existing analogy pairs for auto-complete
    # (preserve user's pairs, only identify relationship)
    existing_analogies: Optional[List[Dict[str, str]]] = Field(
        None,
        description=(
            "Existing bridge map analogy pairs [{left, right}, ...] "
            "for auto-complete mode"
        )
    )
    # Fixed dimension: user-specified dimension that should be preserved
    # (used for tree_map, brace_map, and bridge_map)
    fixed_dimension: Optional[str] = Field(
        None,
        description=(
            "User-specified dimension/relationship pattern that should be "
            "preserved (classification dimension for tree_map, "
            "decomposition dimension for brace_map, "
            "relationship pattern for bridge_map)"
        )
    )
    # Dimension-only mode: user has specified dimension but no topic
    # (used for tree_map and brace_map)
    dimension_only_mode: Optional[bool] = Field(
        None,
        description=(
            "Flag indicating dimension-only mode where user has specified "
            "dimension but no topic (generate topic and children based on "
            "dimension)"
        )
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

        return aliases.get(v_str, v_str)

    class Config:
        """Configuration for GenerateRequest model."""

        json_schema_extra = {
            "example": {
                "prompt": "生成关于光合作用的概念图",
                "diagram_type": "concept_map",
                "language": "zh",
                "llm": "qwen"
            }
        }


class EnhanceRequest(BaseModel):
    """Request model for /api/enhance endpoint"""
    diagram_data: Dict[str, Any] = Field(
        ..., description="Current diagram data to enhance"
    )
    diagram_type: DiagramType = Field(..., description="Type of diagram")
    enhancement_type: str = Field(
        ..., description="Type of enhancement to apply"
    )
    language: Language = Field(
        Language.ZH, description="Language for enhancement"
    )
    llm: LLMModel = Field(LLMModel.QWEN, description="LLM model to use")

    class Config:
        """Configuration for EnhanceRequest model."""

        json_schema_extra = {
            "example": {
                "diagram_data": {"topic": "Example"},
                "diagram_type": "bubble_map",
                "enhancement_type": "expand",
                "language": "zh",
                "llm": "qwen"
            }
        }


class ExportPNGRequest(BaseModel):
    """Request model for /api/export_png endpoint"""
    diagram_data: Dict[str, Any] = Field(
        ..., description="Diagram data to export as PNG"
    )
    diagram_type: DiagramType = Field(..., description="Type of diagram")
    width: Optional[int] = Field(
        1200, ge=400, le=4000, description="PNG width in pixels"
    )
    height: Optional[int] = Field(
        800, ge=300, le=3000, description="PNG height in pixels"
    )
    scale: Optional[int] = Field(
        2, ge=1, le=4, description="Scale factor for high-DPI displays"
    )

    class Config:
        """Configuration for ExportPNGRequest model."""

        json_schema_extra = {
            "example": {
                "diagram_data": {"topic": "Example"},
                "diagram_type": "bubble_map",
                "width": 1200,
                "height": 800,
                "scale": 2
            }
        }


class GeneratePNGRequest(BaseModel):
    """Request model for /api/generate_png endpoint - direct PNG from prompt"""
    prompt: str = Field(
        ..., min_length=1,
        description="Natural language description of diagram"
    )
    language: Optional[Language] = Field(
        Language.ZH,
        description="Language code (en or zh, defaults to Chinese)"
    )
    llm: Optional[LLMModel] = Field(
        LLMModel.QWEN, description="LLM model to use for generation"
    )
    diagram_type: Optional[DiagramType] = Field(
        None, description="Force specific diagram type"
    )
    dimension_preference: Optional[str] = Field(
        None, description="Dimension preference hint"
    )
    width: Optional[int] = Field(
        1200, ge=400, le=4000, description="PNG width in pixels"
    )
    height: Optional[int] = Field(
        800, ge=300, le=3000, description="PNG height in pixels"
    )
    scale: Optional[int] = Field(
        2, ge=1, le=4, description="Scale factor for high-DPI"
    )

    class Config:
        """Configuration for GeneratePNGRequest model."""

        json_schema_extra = {
            "example": {
                "prompt": "Create a mind map about machine learning",
                "language": "en",
                "llm": "qwen",
                "width": 1200,
                "height": 800
            }
        }


class GenerateDingTalkRequest(BaseModel):
    """Request model for /api/generate_dingtalk endpoint"""
    prompt: str = Field(
        ..., min_length=1, description="Natural language description"
    )
    language: Optional[Language] = Field(
        Language.ZH, description="Language code (defaults to Chinese)"
    )
    llm: Optional[LLMModel] = Field(
        LLMModel.QWEN, description="LLM model to use"
    )
    diagram_type: Optional[DiagramType] = Field(
        None, description="Force specific diagram type"
    )
    dimension_preference: Optional[str] = Field(
        None, description="Dimension preference hint"
    )

    class Config:
        """Configuration for GenerateDingTalkRequest model."""

        json_schema_extra = {
            "example": {
                "prompt": "比较猫和狗",
                "language": "zh"
            }
        }


class RecalculateLayoutRequest(BaseModel):
    """Request model for /api/recalculate_mindmap_layout endpoint"""
    spec: Dict[str, Any] = Field(
        ...,
        description="Current diagram specification to recalculate layout for"
    )

    class Config:
        """Configuration for RecalculateLayoutRequest model."""

        json_schema_extra = {
            "example": {
                "spec": {
                    "topic": "中心主题",
                    "children": [
                        {"text": "分支1", "children": []},
                        {"text": "分支2", "children": []}
                    ]
                }
            }
        }


class DiagramCreateRequest(BaseModel):
    """Request model for creating a new diagram"""
    title: str = Field(
        ..., min_length=1, max_length=200, description="Diagram title"
    )
    diagram_type: str = Field(
        ..., description="Type of diagram (e.g., 'mind_map', 'concept_map')"
    )
    spec: Dict[str, Any] = Field(
        ..., description="Diagram specification as JSON"
    )
    language: str = Field('zh', description="Language code (zh or en)")
    # Max ~100KB base64 thumbnail (150000 chars = ~112KB decoded)
    thumbnail: Optional[str] = Field(
        None, max_length=150000,
        description="Base64 encoded thumbnail image (max ~100KB)"
    )

    @field_validator('language')
    @classmethod
    def validate_language(cls, v):
        """Validate language code"""
        if v not in ['zh', 'en']:
            raise ValueError("Language must be 'zh' or 'en'")
        return v

    class Config:
        """Configuration for DiagramCreateRequest model."""

        json_schema_extra = {
            "example": {
                "title": "My Mind Map",
                "diagram_type": "mind_map",
                "spec": {"topic": "Central Topic", "children": []},
                "language": "zh"
            }
        }


class DiagramUpdateRequest(BaseModel):
    """Request model for updating an existing diagram"""
    title: Optional[str] = Field(
        None, min_length=1, max_length=200,
        description="New diagram title"
    )
    spec: Optional[Dict[str, Any]] = Field(
        None, description="Updated diagram specification"
    )
    # Max ~100KB base64 thumbnail (150000 chars = ~112KB decoded)
    thumbnail: Optional[str] = Field(
        None, max_length=150000,
        description="Base64 encoded thumbnail image (max ~100KB)"
    )

    class Config:
        """Configuration for DiagramUpdateRequest model."""

        json_schema_extra = {
            "example": {
                "title": "Updated Title",
                "spec": {"topic": "Updated Topic", "children": []}
            }
        }
