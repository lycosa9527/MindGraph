"""
Request Models
==============

Pydantic models for validating API request payloads.

Author: lycosa9527
Made by: MindSpring Team
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
from .common import DiagramType, LLMModel, Language


class GenerateRequest(BaseModel):
    """Request model for /api/generate endpoint"""
    prompt: str = Field(..., min_length=1, max_length=10000, description="User prompt for diagram generation")
    diagram_type: Optional[DiagramType] = Field(None, description="Diagram type (auto-detected if not provided)")
    language: Language = Field(Language.ZH, description="Language for diagram generation")
    llm: LLMModel = Field(LLMModel.QWEN, description="LLM model to use")
    models: Optional[List[str]] = Field(None, description="List of models for parallel generation (e.g., ['qwen', 'deepseek', 'kimi', 'hunyuan'])")
    dimension_preference: Optional[str] = Field(None, description="Optional dimension preference for certain diagrams")
    
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
    diagram_data: Dict[str, Any] = Field(..., description="Current diagram data to enhance")
    diagram_type: DiagramType = Field(..., description="Type of diagram")
    enhancement_type: str = Field(..., description="Type of enhancement to apply")
    language: Language = Field(Language.ZH, description="Language for enhancement")
    llm: LLMModel = Field(LLMModel.QWEN, description="LLM model to use")
    
    class Config:
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
    diagram_data: Dict[str, Any] = Field(..., description="Diagram data to export as PNG")
    diagram_type: DiagramType = Field(..., description="Type of diagram")
    width: Optional[int] = Field(1200, ge=400, le=4000, description="PNG width in pixels")
    height: Optional[int] = Field(800, ge=300, le=3000, description="PNG height in pixels")
    scale: Optional[int] = Field(2, ge=1, le=4, description="Scale factor for high-DPI displays")
    
    class Config:
        json_schema_extra = {
            "example": {
                "diagram_data": {"topic": "Example"},
                "diagram_type": "bubble_map",
                "width": 1200,
                "height": 800,
                "scale": 2
            }
        }


class AIAssistantRequest(BaseModel):
    """Request model for /api/ai_assistant/stream endpoint (SSE)"""
    message: str = Field(..., min_length=1, max_length=5000, description="User message to AI assistant")
    user_id: str = Field(..., min_length=1, max_length=100, description="Unique user identifier")
    conversation_id: Optional[str] = Field(None, max_length=100, description="Conversation ID for context")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "帮我解释一下概念图的作用",
                "user_id": "user_123",
                "conversation_id": "conv_456"
            }
        }


# ============================================================================
# LEARNING MODE REQUEST MODELS
# ============================================================================

class LearningStartSessionRequest(BaseModel):
    """Request model for /api/learning/start_session endpoint"""
    diagram_type: DiagramType = Field(..., description="Type of diagram for learning")
    spec: Dict[str, Any] = Field(..., description="Diagram specification")
    knocked_out_nodes: List[str] = Field(..., min_items=1, description="Node IDs to knock out for learning")
    language: Language = Field(Language.EN, description="Language for questions")
    
    class Config:
        json_schema_extra = {
            "example": {
                "diagram_type": "bubble_map",
                "spec": {"topic": "Plants", "attributes": ["water", "sunlight"]},
                "knocked_out_nodes": ["attribute_1"],
                "language": "zh"
            }
        }


class LearningValidateAnswerRequest(BaseModel):
    """Request model for /api/learning/validate_answer endpoint"""
    session_id: str = Field(..., description="Learning session ID")
    node_id: str = Field(..., description="Node ID being answered")
    user_answer: str = Field(..., min_length=1, description="Student's answer")
    question: str = Field(..., description="The question that was asked")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")
    language: Language = Field(Language.EN, description="Language for validation")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "learning_123",
                "node_id": "attribute_3",
                "user_answer": "氧气",
                "question": "植物光合作用产生什么气体?",
                "language": "zh"
            }
        }


class LearningHintRequest(BaseModel):
    """Request model for /api/learning/get_hint endpoint"""
    session_id: str = Field(..., description="Learning session ID")
    node_id: str = Field(..., description="Node ID needing hint")
    question: str = Field(..., description="The question")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")
    hint_level: int = Field(1, ge=1, le=3, description="Hint level (1=subtle, 3=direct)")
    language: Language = Field(Language.EN, description="Language for hint")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "learning_123",
                "node_id": "attribute_3",
                "question": "What gas do plants produce?",
                "hint_level": 1,
                "language": "en"
            }
        }


class FrontendLogRequest(BaseModel):
    """Request model for /api/frontend_log endpoint"""
    level: str = Field(..., description="Log level (debug, info, warn, error)")
    message: str = Field(..., max_length=1000, description="Log message")
    source: Optional[str] = Field(None, description="Source component")
    timestamp: Optional[float] = Field(None, description="Client timestamp")
    
    @field_validator('level')
    @classmethod
    def validate_level(cls, v):
        valid_levels = ['debug', 'info', 'warn', 'error']
        if v.lower() not in valid_levels:
            raise ValueError(f"Level must be one of {valid_levels}")
        return v.lower()


class LearningVerifyUnderstandingRequest(BaseModel):
    """Request model for /api/learning/verify_understanding endpoint"""
    session_id: str = Field(..., description="Learning session ID")
    node_id: str = Field(..., description="Node ID being verified")
    user_explanation: str = Field(..., min_length=1, max_length=1000, description="User's explanation of understanding")
    language: Language = Field(Language.EN, description="Language for verification feedback")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "learning_123",
                "node_id": "attribute_3",
                "user_explanation": "光合作用通过叶绿素吸收光能，将二氧化碳和水转化为氧气和葡萄糖",
                "language": "zh"
            }
        }


class ThinkingModeRequest(BaseModel):
    """Request model for ThinkGuide (Thinking Mode) SSE streaming endpoint"""
    message: str = Field("", description="User message (empty for initial state)")
    user_id: str = Field(..., min_length=1, max_length=100, description="User identifier")
    session_id: str = Field(..., min_length=1, max_length=100, description="Thinking session ID")
    diagram_type: str = Field(..., description="Diagram type (e.g., 'circle_map')")
    diagram_data: Dict[str, Any] = Field(..., description="Complete diagram structure")
    current_state: str = Field(..., description="Current workflow state")
    selected_node: Optional[Dict[str, Any]] = Field(None, description="Currently selected node (optional)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "5th grade science, understanding photosynthesis",
                "user_id": "user123",
                "session_id": "thinking_abc",
                "diagram_type": "circle_map",
                "diagram_data": {
                    "center": {"text": "Photosynthesis"},
                    "children": [
                        {"id": "1", "text": "Sunlight"},
                        {"id": "2", "text": "Water"},
                        {"id": "3", "text": "Carbon Dioxide"}
                    ]
                },
                "current_state": "CONTEXT_GATHERING",
                "selected_node": {
                    "id": "1",
                    "text": "Sunlight",
                    "type": "circle"
                }
            }
        }
