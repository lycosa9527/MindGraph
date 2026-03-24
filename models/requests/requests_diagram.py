"""Diagram Generation and Storage Request Models.

Pydantic models for validating diagram generation, export, and storage API requests.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field, field_validator, model_validator

from utils.prompt_output_languages import is_prompt_output_language

from ..common import DiagramType, LLMModel


def _validate_prompt_output_language(value: str) -> str:
    """Ensure API language is in the prompt-output registry."""
    if not is_prompt_output_language(value):
        raise ValueError("Language must be a supported generation language code")
    return value


def _coerce_prompt_output_language(value: str) -> str:
    """Default invalid codes to zh (lenient validators for optional fields)."""
    lowered = (value or 'zh').lower().strip()
    if is_prompt_output_language(lowered):
        return lowered
    return 'zh'


class GenerateRequest(BaseModel):
    """Request model for /api/generate endpoint"""
    prompt: str = Field(
        default='',
        max_length=10000,
        description="User prompt for diagram generation (may be empty for dimension-only mode)",
    )
    diagram_type: Optional[DiagramType] = Field(
        None, description="Diagram type (auto-detected if not provided)"
    )
    language: str = Field(
        'zh', description="Language code for diagram generation (see prompt output registry)"
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
    diagram_id: Optional[str] = Field(
        None,
        description="Current saved diagram id (for collaboration / owner checks on autocomplete)",
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
    # Concept map: relationship-only mode (generate label for link between two concepts)
    concept_map_relationship_only: Optional[bool] = Field(
        None,
        description="Generate only the relationship label between two concepts"
    )
    concept_a: Optional[str] = Field(
        None,
        description="First concept text for relationship-only mode"
    )
    concept_b: Optional[str] = Field(
        None,
        description="Second concept text for relationship-only mode"
    )
    concept_map_topic: Optional[str] = Field(
        None,
        description="Topic of the concept map (main concept) for focused relationship generation"
    )
    link_direction: Optional[str] = Field(
        None,
        description=(
            "Concept map link arrow direction: 'source_to_target' (A→B), "
            "'target_to_source' (B→A), 'both' (bidirectional), 'none' (parallel/no arrow)"
        )
    )

    @field_validator('language')
    @classmethod
    def validate_generate_language(cls, value: str) -> str:
        """Reject unknown generation language codes."""
        return _validate_prompt_output_language(value)

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

    @model_validator(mode='after')
    def validate_prompt_or_dimension(self):
        """Allow empty prompt only when dimension-only mode (fixed_dimension or dimension_only_mode)."""
        prompt_empty = not (self.prompt or '').strip()
        has_fixed_dimension = self.fixed_dimension and str(self.fixed_dimension).strip()
        dimension_only_mode = self.dimension_only_mode is True

        if prompt_empty and not (has_fixed_dimension or dimension_only_mode):
            raise ValueError(
                "Prompt is required unless fixed_dimension or dimension_only_mode is provided"
            )
        return self

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
    language: str = Field(
        'zh', description="Language code for enhancement"
    )
    llm: LLMModel = Field(LLMModel.QWEN, description="LLM model to use")

    @field_validator('language')
    @classmethod
    def validate_enhance_language(cls, value: str) -> str:
        """Reject unknown generation language codes."""
        return _validate_prompt_output_language(value)

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
    language: str = Field(
        'zh',
        description="Language code for diagram text (prompt output registry)"
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

    @field_validator('language')
    @classmethod
    def validate_generate_png_language(cls, value: str) -> str:
        """Reject unknown generation language codes."""
        return _validate_prompt_output_language(value)

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
    language: str = Field(
        'zh', description="Language code (prompt output registry)"
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

    @field_validator('language')
    @classmethod
    def validate_dingtalk_language(cls, value: str) -> str:
        """Reject unknown generation language codes."""
        return _validate_prompt_output_language(value)

    class Config:
        """Configuration for GenerateDingTalkRequest model."""

        json_schema_extra = {
            "example": {
                "prompt": "比较猫和狗",
                "language": "zh"
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
    def validate_language(cls, value: str) -> str:
        """Reject unknown generation language codes."""
        return _validate_prompt_output_language(value)

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
    edit_count: Optional[int] = Field(
        None, ge=0, le=1000,
        description="Number of content edits (add/delete/change nodes) since last save"
    )

    class Config:
        """Configuration for DiagramUpdateRequest model."""

        json_schema_extra = {
            "example": {
                "title": "Updated Title",
                "spec": {"topic": "Updated Topic", "children": []}
            }
        }


class FocusQuestionReviewRequest(BaseModel):
    """Request for AI validation and refinement of a concept-map focus question."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="User's proposed focus question for the concept map",
    )
    language: str = Field(
        default='zh',
        description="Response language: zh or en",
    )

    @field_validator('language')
    @classmethod
    def normalize_language(cls, value: str) -> str:
        """Map focus-question review language to a supported generation code."""
        return _coerce_prompt_output_language(value)


class FocusQuestionSuggestionsRequest(BaseModel):
    """Request for streaming / batch focus-question suggestions (separate from validation)."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="User's proposed focus question",
    )
    language: str = Field(default='zh', description="zh or en")
    avoid: Optional[List[str]] = Field(
        default=None,
        description="Previously shown suggestions to avoid repeating",
    )

    @field_validator('language')
    @classmethod
    def normalize_language_suggestions(cls, value: str) -> str:
        """Map suggestion request language to a supported generation code."""
        return _coerce_prompt_output_language(value)

    @field_validator('avoid')
    @classmethod
    def cap_avoid_list(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        """Limit list size and string length."""
        if not value:
            return value
        out: List[str] = []
        for item in value[:80]:
            s = str(item).strip()
            if s and len(s) <= 400:
                out.append(s)
        return out or None


class RootConceptGenerateRequest(BaseModel):
    """Derive a Novak-style root concept from the concept-map focus question (Tab on root concept node)."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Focus question (topic) text",
    )
    language: str = Field(default='zh', description="zh or en")

    @field_validator('language')
    @classmethod
    def normalize_language_root_concept(cls, value: str) -> str:
        """Map root-concept generation language to a supported generation code."""
        return _coerce_prompt_output_language(value)


class RootConceptSuggestionsRequest(BaseModel):
    """Streaming root-concept suggestions (3 models, 5 strings each per wave)."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Focus question (topic) text",
    )
    language: str = Field(default='zh', description="zh or en")
    avoid: Optional[List[str]] = Field(
        default=None,
        description="Previously shown root suggestions to avoid repeating",
    )

    @field_validator('language')
    @classmethod
    def normalize_language_root_suggestions(cls, value: str) -> str:
        """Map root-concept suggestion language to a supported generation code."""
        return _coerce_prompt_output_language(value)

    @field_validator('avoid')
    @classmethod
    def cap_avoid_list_root(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        """Limit list size and string length."""
        if not value:
            return value
        out: List[str] = []
        for item in value[:80]:
            s = str(item).strip()
            if s and len(s) <= 400:
                out.append(s)
        return out or None


class WorkshopStartRequest(BaseModel):
    """Optional body for POST /api/diagrams/{id}/workshop/start."""

    visibility: str = Field(
        default="organization",
        description="organization (校内) or network (共同)",
    )
    duration: str = Field(
        default="today",
        description="Session window: 1h | today | 2d (allowed set depends on visibility)",
    )

    @field_validator("visibility")
    @classmethod
    def validate_workshop_visibility(cls, value: str) -> str:
        """Allow only organization or network."""
        if value not in ("organization", "network"):
            raise ValueError("visibility must be organization or network")
        return value

    @field_validator("duration")
    @classmethod
    def validate_workshop_duration(cls, value: str) -> str:
        """Allow only known preset keys."""
        if value not in ("1h", "today", "2d"):
            raise ValueError("duration must be 1h, today, or 2d")
        return value


class WorkshopJoinOrganizationRequest(BaseModel):
    """Body for POST /api/workshop/join-organization (校内 join by diagram)."""

    diagram_id: str = Field(..., min_length=10, max_length=40)
