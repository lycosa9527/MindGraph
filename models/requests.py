"""
Request Models
==============

Pydantic models for validating API request payloads.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
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
    models: Optional[List[str]] = Field(None, description="List of models for parallel generation (e.g., ['qwen', 'deepseek', 'kimi', 'doubao'])")
    dimension_preference: Optional[str] = Field(None, description="Optional dimension preference for certain diagrams")
    request_type: Optional[str] = Field('diagram_generation', description="Request type for token tracking: 'diagram_generation' or 'autocomplete'")
    # Bridge map specific: existing analogy pairs for auto-complete (preserve user's pairs, only identify relationship)
    existing_analogies: Optional[List[Dict[str, str]]] = Field(None, description="Existing bridge map analogy pairs [{left, right}, ...] for auto-complete mode")
    # Fixed dimension: user-specified dimension that should be preserved (used for tree_map, brace_map, and bridge_map)
    fixed_dimension: Optional[str] = Field(None, description="User-specified dimension/relationship pattern that should be preserved (classification dimension for tree_map, decomposition dimension for brace_map, relationship pattern for bridge_map)")
    # Dimension-only mode: user has specified dimension but no topic (used for tree_map and brace_map)
    dimension_only_mode: Optional[bool] = Field(None, description="Flag indicating dimension-only mode where user has specified dimension but no topic (generate topic and children based on dimension)")
    
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
    language: Optional[Language] = Field(Language.ZH, description="Language code (en or zh, defaults to Chinese)")
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


class AIAssistantFile(BaseModel):
    """File object for AI assistant requests (Dify API compatible)"""
    type: str = Field(..., description="File type: document, image, audio, video, custom")
    transfer_method: str = Field(..., description="Transfer method: remote_url or local_file")
    url: Optional[str] = Field(None, description="File URL (for remote_url transfer method)")
    upload_file_id: Optional[str] = Field(None, description="Uploaded file ID (for local_file transfer method)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "image",
                "transfer_method": "remote_url",
                "url": "https://example.com/image.png"
            }
        }


class AIAssistantRequest(BaseModel):
    """Request model for /api/ai_assistant/stream endpoint (SSE)
    
    Supports Dify Chatflow API with file uploads for Vision/document processing.
    """
    message: str = Field(
        ..., 
        min_length=1, 
        max_length=5000, 
        description="User message to AI assistant (use 'start' to trigger Dify conversation opener)"
    )
    user_id: str = Field(..., min_length=1, max_length=100, description="Unique user identifier")
    conversation_id: Optional[str] = Field(None, max_length=100, description="Conversation ID for context (null for new conversation)")
    files: Optional[List[AIAssistantFile]] = Field(None, description="Files for Vision/document processing")
    inputs: Optional[Dict[str, Any]] = Field(None, description="App-defined variable values")
    auto_generate_name: bool = Field(True, description="Auto-generate conversation title")
    workflow_id: Optional[str] = Field(None, description="Specific workflow version ID")
    trace_id: Optional[str] = Field(None, description="Trace ID for distributed tracing")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "帮我解释一下概念图的作用",
                "user_id": "user_123",
                "conversation_id": "conv_456",
                "files": [
                    {
                        "type": "image",
                        "transfer_method": "remote_url",
                        "url": "https://example.com/diagram.png"
                    }
                ]
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
    language: str = Field('en', description="UI language (en or zh)")
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
    language: str = Field('en', description="UI language (en or zh)")
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
# TAB MODE REQUEST MODELS
# ============================================================================

class TabSuggestionRequest(BaseModel):
    """Request model for /api/tab_suggestions endpoint (editing autocomplete)"""
    mode: str = Field("autocomplete", description="Mode: 'autocomplete' for editing suggestions")
    diagram_type: DiagramType = Field(..., description="Type of diagram")
    main_topics: List[str] = Field(..., min_items=1, description="Main topic nodes")
    node_category: Optional[str] = Field(None, description="Node category")
    partial_input: str = Field(..., description="User's current partial input")
    existing_nodes: Optional[List[str]] = Field(None, description="Existing nodes in same category")
    language: Language = Field(Language.EN, description="Language code")
    llm: LLMModel = Field(LLMModel.QWEN, description="LLM model to use")
    cursor_position: Optional[int] = Field(None, description="Cursor position in input")
    
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
    mode: str = Field("expansion", description="Mode: 'expansion' for node expansion")
    diagram_type: DiagramType = Field(..., description="Type of diagram")
    node_id: str = Field(..., description="Node ID to expand")
    node_text: str = Field(..., description="Text of the node to expand")
    node_type: str = Field("branch", description="Type of node (branch, category, step, part)")
    main_topic: Optional[str] = Field(None, description="Main topic/center node text")
    existing_children: Optional[List[str]] = Field(None, description="Existing children nodes")
    num_children: int = Field(4, ge=1, le=10, description="Number of children to generate")
    language: Language = Field(Language.EN, description="Language code")
    llm: LLMModel = Field(LLMModel.QWEN, description="LLM model to use")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")
    
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
            raise ValueError("Phone number must contain only digits. Please enter a valid 11-digit Chinese mobile number.")
        if len(v) < 11:
            raise ValueError(f"Phone number is too short ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if len(v) > 11:
            raise ValueError(f"Phone number is too long ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if not v.startswith('1'):
            raise ValueError("Chinese mobile numbers must start with 1. Please enter a valid 11-digit number starting with 1.")
        return v
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate name has no numbers"""
        if len(v) < 2:
            raise ValueError(f"Name is too short ({len(v)} character(s)). Must be at least 2 characters.")
        if any(char.isdigit() for char in v):
            raise ValueError("Name cannot contain numbers. Please enter your name using letters only.")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "phone": "13812345678",
                "password": "Teacher123!",
                "name": "Zhang Wei",
                "invitation_code": "DEMO-A1B2C",
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


# ============================================================================
# SMS VERIFICATION REQUEST MODELS
# ============================================================================

class SendSMSCodeRequest(BaseModel):
    """Request model for sending SMS verification code"""
    phone: str = Field(..., min_length=11, max_length=11, description="11-digit Chinese mobile number")
    purpose: str = Field(..., description="Purpose: 'register', 'login', or 'reset_password'")
    captcha: str = Field(..., min_length=4, max_length=4, description="4-character captcha code")
    captcha_id: str = Field(..., description="Captcha session ID")
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError("Phone number must contain only digits. Please enter a valid 11-digit Chinese mobile number.")
        if len(v) < 11:
            raise ValueError(f"Phone number is too short ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if len(v) > 11:
            raise ValueError(f"Phone number is too long ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if not v.startswith('1'):
            raise ValueError("Chinese mobile numbers must start with 1. Please enter a valid 11-digit number starting with 1.")
        return v
    
    @field_validator('purpose')
    @classmethod
    def validate_purpose(cls, v):
        """Validate SMS purpose"""
        valid_purposes = ['register', 'login', 'reset_password', 'change_phone']
        if v not in valid_purposes:
            raise ValueError(f"Purpose must be one of: {', '.join(valid_purposes)}")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "phone": "13812345678",
                "purpose": "register",
                "captcha": "AB3D",
                "captcha_id": "uuid-captcha-session"
            }
        }


class VerifySMSCodeRequest(BaseModel):
    """Request model for verifying SMS code (standalone verification)"""
    phone: str = Field(..., min_length=11, max_length=11, description="11-digit Chinese mobile number")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit SMS verification code")
    purpose: str = Field(..., description="Purpose: 'register', 'login', or 'reset_password'")
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError("Phone number must contain only digits. Please enter a valid 11-digit Chinese mobile number.")
        if len(v) < 11:
            raise ValueError(f"Phone number is too short ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if len(v) > 11:
            raise ValueError(f"Phone number is too long ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if not v.startswith('1'):
            raise ValueError("Chinese mobile numbers must start with 1. Please enter a valid 11-digit number starting with 1.")
        return v
    
    @field_validator('code')
    @classmethod
    def validate_code(cls, v):
        """Validate 6-digit SMS code"""
        if not v.isdigit():
            raise ValueError("SMS verification code must contain only digits. Please enter the 6-digit code sent to your phone.")
        if len(v) != 6:
            raise ValueError(f"SMS verification code must be exactly 6 digits. You entered {len(v)} digit(s).")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "phone": "13812345678",
                "code": "123456",
                "purpose": "register"
            }
        }


class RegisterWithSMSRequest(BaseModel):
    """Request model for registration with SMS verification"""
    phone: str = Field(..., min_length=11, max_length=11, description="11-digit Chinese mobile number")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    name: str = Field(..., min_length=2, description="Teacher's name (required, min 2 chars, no numbers)")
    invitation_code: str = Field(..., description="Invitation code for registration")
    sms_code: str = Field(..., min_length=6, max_length=6, description="6-digit SMS verification code")
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError("Phone number must contain only digits. Please enter a valid 11-digit Chinese mobile number.")
        if len(v) < 11:
            raise ValueError(f"Phone number is too short ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if len(v) > 11:
            raise ValueError(f"Phone number is too long ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if not v.startswith('1'):
            raise ValueError("Chinese mobile numbers must start with 1. Please enter a valid 11-digit number starting with 1.")
        return v
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate name has no numbers"""
        if len(v) < 2:
            raise ValueError(f"Name is too short ({len(v)} character(s)). Must be at least 2 characters.")
        if any(char.isdigit() for char in v):
            raise ValueError("Name cannot contain numbers. Please enter your name using letters only.")
        return v
    
    @field_validator('sms_code')
    @classmethod
    def validate_sms_code(cls, v):
        """Validate 6-digit SMS code"""
        if not v.isdigit():
            raise ValueError("SMS verification code must contain only digits. Please enter the 6-digit code sent to your phone.")
        if len(v) != 6:
            raise ValueError(f"SMS verification code must be exactly 6 digits. You entered {len(v)} digit(s).")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "phone": "13812345678",
                "password": "Teacher123!",
                "name": "Zhang Wei",
                "invitation_code": "DEMO-A1B2C",
                "sms_code": "123456"
            }
        }


class LoginWithSMSRequest(BaseModel):
    """Request model for login with SMS verification"""
    phone: str = Field(..., min_length=11, max_length=11, description="11-digit Chinese mobile number")
    sms_code: str = Field(..., min_length=6, max_length=6, description="6-digit SMS verification code")
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError("Phone number must contain only digits. Please enter a valid 11-digit Chinese mobile number.")
        if len(v) < 11:
            raise ValueError(f"Phone number is too short ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if len(v) > 11:
            raise ValueError(f"Phone number is too long ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if not v.startswith('1'):
            raise ValueError("Chinese mobile numbers must start with 1. Please enter a valid 11-digit number starting with 1.")
        return v
    
    @field_validator('sms_code')
    @classmethod
    def validate_sms_code(cls, v):
        """Validate 6-digit SMS code"""
        if not v.isdigit():
            raise ValueError("SMS verification code must contain only digits. Please enter the 6-digit code sent to your phone.")
        if len(v) != 6:
            raise ValueError(f"SMS verification code must be exactly 6 digits. You entered {len(v)} digit(s).")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "phone": "13812345678",
                "sms_code": "123456"
            }
        }


class ChangePasswordRequest(BaseModel):
    """Request model for /api/auth/change-password endpoint"""
    current_password: str = Field(..., min_length=4, description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters)")


class ResetPasswordWithSMSRequest(BaseModel):
    """Request model for password reset with SMS verification"""
    phone: str = Field(..., min_length=11, max_length=11, description="11-digit Chinese mobile number")
    sms_code: str = Field(..., min_length=6, max_length=6, description="6-digit SMS verification code")
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError("Phone number must contain only digits. Please enter a valid 11-digit Chinese mobile number.")
        if len(v) < 11:
            raise ValueError(f"Phone number is too short ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if len(v) > 11:
            raise ValueError(f"Phone number is too long ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if not v.startswith('1'):
            raise ValueError("Chinese mobile numbers must start with 1. Please enter a valid 11-digit number starting with 1.")
        return v
    
    @field_validator('sms_code')
    @classmethod
    def validate_sms_code(cls, v):
        """Validate 6-digit SMS code"""
        if not v.isdigit():
            raise ValueError("SMS verification code must contain only digits. Please enter the 6-digit code sent to your phone.")
        if len(v) != 6:
            raise ValueError(f"SMS verification code must be exactly 6 digits. You entered {len(v)} digit(s).")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "phone": "13812345678",
                "sms_code": "123456",
                "new_password": "NewPassword123!"
            }
        }


class SendChangePhoneSMSRequest(BaseModel):
    """Request model for sending SMS code to new phone number for phone change"""
    new_phone: str = Field(..., min_length=11, max_length=11, description="New 11-digit Chinese mobile number")
    captcha: str = Field(..., min_length=4, max_length=4, description="4-character captcha code")
    captcha_id: str = Field(..., description="Captcha session ID")
    
    @field_validator('new_phone')
    @classmethod
    def validate_new_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError("Phone number must contain only digits. Please enter a valid 11-digit Chinese mobile number.")
        if len(v) < 11:
            raise ValueError(f"Phone number is too short ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if len(v) > 11:
            raise ValueError(f"Phone number is too long ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if not v.startswith('1'):
            raise ValueError("Chinese mobile numbers must start with 1. Please enter a valid 11-digit number starting with 1.")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "new_phone": "13987654321",
                "captcha": "AB3D",
                "captcha_id": "uuid-captcha-session"
            }
        }


class ChangePhoneRequest(BaseModel):
    """Request model for completing phone number change with SMS verification"""
    new_phone: str = Field(..., min_length=11, max_length=11, description="New 11-digit Chinese mobile number")
    sms_code: str = Field(..., min_length=6, max_length=6, description="6-digit SMS verification code")
    
    @field_validator('new_phone')
    @classmethod
    def validate_new_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError("Phone number must contain only digits. Please enter a valid 11-digit Chinese mobile number.")
        if len(v) < 11:
            raise ValueError(f"Phone number is too short ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if len(v) > 11:
            raise ValueError(f"Phone number is too long ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if not v.startswith('1'):
            raise ValueError("Chinese mobile numbers must start with 1. Please enter a valid 11-digit number starting with 1.")
        return v
    
    @field_validator('sms_code')
    @classmethod
    def validate_sms_code(cls, v):
        """Validate 6-digit SMS code"""
        if not v.isdigit():
            raise ValueError("SMS verification code must contain only digits. Please enter the 6-digit code sent to your phone.")
        if len(v) != 6:
            raise ValueError(f"SMS verification code must be exactly 6 digits. You entered {len(v)} digit(s).")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "new_phone": "13987654321",
                "sms_code": "123456"
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
