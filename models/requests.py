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
    request_type: Optional[str] = Field('diagram_generation', description="Request type for token tracking: 'diagram_generation' or 'autocomplete'")
    # Bridge map specific: existing analogy pairs for auto-complete (preserve user's pairs, only identify relationship)
    existing_analogies: Optional[List[Dict[str, str]]] = Field(None, description="Existing bridge map analogy pairs [{left, right}, ...] for auto-complete mode")
    # Bridge map specific: fixed dimension/relationship that user has already specified (should not be changed by LLM)
    fixed_dimension: Optional[str] = Field(None, description="User-specified relationship pattern for bridge map that should be preserved")
    
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


class GeneratePNGRequest(BaseModel):
    """Request model for /api/generate_png endpoint - direct PNG from prompt"""
    prompt: str = Field(..., min_length=1, description="Natural language description of diagram")
    language: Optional[Language] = Field(Language.EN, description="Language code (en or zh)")
    llm: Optional[LLMModel] = Field(LLMModel.QWEN, description="LLM model to use for generation")
    diagram_type: Optional[DiagramType] = Field(None, description="Force specific diagram type")
    dimension_preference: Optional[str] = Field(None, description="Dimension preference hint")
    width: Optional[int] = Field(1200, ge=400, le=4000, description="PNG width in pixels")
    height: Optional[int] = Field(800, ge=300, le=3000, description="PNG height in pixels")
    scale: Optional[int] = Field(2, ge=1, le=4, description="Scale factor for high-DPI")
    
    class Config:
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
    prompt: str = Field(..., min_length=1, description="Natural language description")
    language: Optional[Language] = Field(Language.ZH, description="Language code (defaults to Chinese)")
    llm: Optional[LLMModel] = Field(LLMModel.QWEN, description="LLM model to use")
    diagram_type: Optional[DiagramType] = Field(None, description="Force specific diagram type")
    dimension_preference: Optional[str] = Field(None, description="Dimension preference hint")
    
    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "比较猫和狗",
                "language": "zh"
            }
        }


class AIAssistantRequest(BaseModel):
    """Request model for /api/ai_assistant/stream endpoint (SSE)"""
    message: str = Field(
        ..., 
        min_length=1, 
        max_length=5000, 
        description="User message to AI assistant (use 'start' to trigger Dify conversation opener)"
    )
    user_id: str = Field(..., min_length=1, max_length=100, description="Unique user identifier")
    conversation_id: Optional[str] = Field(None, max_length=100, description="Conversation ID for context (null for new conversation)")
    
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
    message: str = Field(..., max_length=5000, description="Log message")
    source: Optional[str] = Field(None, description="Source component")
    timestamp: Optional[str] = Field(None, description="Client timestamp (ISO format)")
    
    @field_validator('level')
    @classmethod
    def validate_level(cls, v):
        valid_levels = ['debug', 'info', 'warn', 'error']
        if v.lower() not in valid_levels:
            raise ValueError(f"Level must be one of {valid_levels}")
        return v.lower()


class FrontendLogBatchRequest(BaseModel):
    """Request model for /api/frontend_log_batch endpoint (batched logs)"""
    logs: List[FrontendLogRequest] = Field(..., min_items=1, max_items=50, description="Batch of log entries")
    batch_size: int = Field(..., description="Number of logs in this batch")
    
    class Config:
        json_schema_extra = {
            "example": {
                "logs": [
                    {
                        "level": "info",
                        "message": "[ToolbarManager] Auto-complete started",
                        "source": "ToolbarManager",
                        "timestamp": "2025-10-11T12:34:56.789Z"
                    },
                    {
                        "level": "debug",
                        "message": "[Editor] Rendering diagram",
                        "source": "Editor",
                        "timestamp": "2025-10-11T12:34:57.123Z"
                    }
                ],
                "batch_size": 2
            }
        }


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
    message: str = Field("", description="User message")
    user_id: str = Field(..., min_length=1, max_length=100, description="User identifier")
    session_id: str = Field(..., min_length=1, max_length=100, description="Thinking session ID")
    diagram_type: str = Field(..., description="Diagram type (e.g., 'circle_map')")
    diagram_data: Dict[str, Any] = Field(..., description="Complete diagram structure")
    current_state: str = Field(..., description="Current workflow state")
    selected_node: Optional[Dict[str, Any]] = Field(None, description="Currently selected node (optional)")
    is_initial_greeting: bool = Field(False, description="If True, agent should greet user (for new sessions only)")
    language: str = Field('en', description="UI language (en or zh)")
    
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


# ============================================================================
# NODE PALETTE REQUEST MODELS
# ============================================================================

class NodePaletteStartRequest(BaseModel):
    """Request model for /thinking_mode/node_palette/start endpoint"""
    session_id: str = Field(..., min_length=1, max_length=100, description="Node Palette session ID")
    diagram_type: str = Field(..., description="Diagram type ('circle_map', 'bubble_map', 'double_bubble_map', 'tree_map', etc.)")
    diagram_data: Dict[str, Any] = Field(..., description="Current diagram data")
    educational_context: Optional[Dict[str, Any]] = Field(None, description="Educational context (grade level, subject, etc.)")
    user_id: Optional[str] = Field(None, description="User identifier for analytics")
    mode: Optional[str] = Field('similarities', description="Mode for double bubble map: 'similarities' or 'differences'")
    # NEW: Stage-based generation for tree maps
    stage: Optional[str] = Field('categories', description="Generation stage for tree maps: 'dimensions', 'categories', or 'children'")
    stage_data: Optional[Dict[str, Any]] = Field(None, description="Stage-specific data (e.g., {'dimension': 'Habitat', 'category_name': 'Water Animals'})")
    
    class Config:
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
    session_id: str = Field(..., min_length=1, max_length=100, description="Node Palette session ID")
    diagram_type: str = Field(..., description="Diagram type ('circle_map', 'bubble_map', 'double_bubble_map', 'tree_map', etc.)")
    center_topic: str = Field(..., min_length=1, description="Center topic from diagram")
    educational_context: Optional[Dict[str, Any]] = Field(None, description="Educational context")
    mode: Optional[str] = Field('similarities', description="Mode for double bubble map: 'similarities' or 'differences'")
    # NEW: Stage-based generation for tree maps
    stage: Optional[str] = Field('categories', description="Generation stage for tree maps: 'dimensions', 'categories', or 'children'")
    stage_data: Optional[Dict[str, Any]] = Field(None, description="Stage-specific data (e.g., {'dimension': 'Habitat', 'category_name': 'Water Animals'})")
    
    class Config:
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
    session_id: str = Field(..., min_length=1, max_length=100, description="Node Palette session ID")
    node_id: str = Field(..., description="ID of the node being selected/deselected")
    selected: bool = Field(..., description="True if selected, False if deselected")
    node_text: str = Field(..., max_length=200, description="Text content of the node")
    
    class Config:
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
    session_id: str = Field(..., min_length=1, max_length=100, description="Node Palette session ID")
    selected_node_ids: List[str] = Field(..., min_items=0, description="List of selected node IDs")
    total_nodes_generated: int = Field(..., ge=0, description="Total number of nodes generated")
    batches_loaded: int = Field(..., ge=1, description="Number of batches loaded")
    diagram_type: Optional[str] = Field(None, description="Diagram type for cleanup in generator")
    
    class Config:
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
    session_id: str = Field(..., min_length=1, max_length=100, description="Node Palette session ID")
    diagram_type: Optional[str] = Field(None, description="Diagram type for cleanup in generator")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "palette_abc123",
                "diagram_type": "circle_map"
            }
        }


# ============================================================================
# AUTHENTICATION REQUEST MODELS
# ============================================================================

class RegisterRequest(BaseModel):
    """Request model for user registration"""
    phone: str = Field(..., min_length=11, max_length=11, description="11-digit Chinese mobile number")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    name: str = Field(..., min_length=2, description="Teacher's name (required, min 2 chars, no numbers)")
    invitation_code: str = Field(..., description="Invitation code for registration (automatically binds to school)")
    captcha: str = Field(..., min_length=4, max_length=4, description="4-character captcha code")
    captcha_id: str = Field(..., description="Captcha session ID")
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError("Phone must contain only digits")
        if len(v) != 11:
            raise ValueError("Phone must be exactly 11 digits")
        if not v.startswith('1'):
            raise ValueError("Chinese mobile numbers start with 1")
        return v
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate name has no numbers"""
        if any(char.isdigit() for char in v):
            raise ValueError("Name cannot contain numbers")
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "phone": "13812345678",
                "password": "Teacher123!",
                "name": "Zhang Wei",
                "invitation_code": "DEMO2024",
                "captcha": "AB3D",
                "captcha_id": "uuid-captcha-session"
            }
        }


class LoginRequest(BaseModel):
    """Request model for user login"""
    phone: str = Field(..., description="User phone number")
    password: str = Field(..., description="User password")
    captcha: str = Field(..., min_length=4, max_length=4, description="4-character captcha code")
    captcha_id: str = Field(..., description="Captcha session ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "phone": "13812345678",
                "password": "Teacher123!",
                "captcha": "AB3D",
                "captcha_id": "uuid-captcha-session"
            }
        }


class DemoPasskeyRequest(BaseModel):
    """Request model for demo mode passkey verification"""
    passkey: str = Field(..., min_length=6, max_length=6, description="6-digit demo passkey")
    
    @field_validator('passkey')
    @classmethod
    def validate_passkey(cls, v):
        """Validate 6-digit passkey"""
        if not v.isdigit():
            raise ValueError("Passkey must contain only digits")
        if len(v) != 6:
            raise ValueError("Passkey must be exactly 6 digits")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "passkey": "888888"
            }
        }


class FeedbackRequest(BaseModel):
    """Request model for /api/feedback endpoint"""
    message: str = Field(..., min_length=1, max_length=5000, description="Feedback message content")
    captcha_id: str = Field(..., description="Captcha session ID from /api/auth/captcha/generate")
    captcha: str = Field(..., min_length=4, max_length=4, description="User-entered captcha code")
    user_id: Optional[str] = Field(None, description="User ID if available")
    user_name: Optional[str] = Field(None, description="User name if available")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "The diagram export feature is not working properly.",
                "captcha_id": "uuid-here",
                "captcha": "ABCD",
                "user_id": "user123",
                "user_name": "John Doe"
            }
        }


class RecalculateLayoutRequest(BaseModel):
    """Request model for /api/recalculate_mindmap_layout endpoint"""
    spec: Dict[str, Any] = Field(..., description="Current diagram specification to recalculate layout for")
    
    class Config:
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
