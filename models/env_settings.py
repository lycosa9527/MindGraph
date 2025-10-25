"""
Environment Settings Validation Models
======================================

Pydantic models for validating .env configuration settings.

These models provide:
- Type validation for all environment variables
- Range constraints for numeric values
- Enum validation for choice fields
- URL format validation
- Password/secret field marking
- Category grouping for UI organization

Author: lycosa9527
Made by: MindSpring Team
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator, HttpUrl
from enum import Enum


# ============================================================================
# ENUMS FOR VALIDATION
# ============================================================================

class LogLevel(str, Enum):
    """Valid logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AuthMode(str, Enum):
    """Valid authentication modes"""
    STANDARD = "standard"
    ENTERPRISE = "enterprise"
    DEMO = "demo"


class GraphLanguage(str, Enum):
    """Valid graph languages"""
    ZH = "zh"
    EN = "en"


# ============================================================================
# SETTINGS MODELS BY CATEGORY
# ============================================================================

class AppSettings(BaseModel):
    """Application server settings"""
    __category__ = "Application Server"
    
    HOST: str = Field(
        default="0.0.0.0",
        description="Server host address"
    )
    PORT: int = Field(
        default=9527,
        ge=1,
        le=65535,
        description="Server port number"
    )
    DEBUG: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    EXTERNAL_HOST: Optional[str] = Field(
        default=None,
        description="Public IP address for external access (optional)"
    )
    
    @field_validator('PORT')
    @classmethod
    def validate_port(cls, v):
        if not (1 <= v <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {v}")
        return v


class QwenAPISettings(BaseModel):
    """Qwen API configuration"""
    __category__ = "Qwen API"
    
    QWEN_API_KEY: str = Field(
        ...,
        min_length=10,
        description="Qwen API key (required)"
    )
    QWEN_API_URL: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        description="Qwen API endpoint URL"
    )
    QWEN_MODEL_CLASSIFICATION: str = Field(
        default="qwen-turbo",
        description="Model for classification tasks (faster, cheaper)"
    )
    QWEN_MODEL_GENERATION: str = Field(
        default="qwen-plus",
        description="Model for generation tasks (higher quality)"
    )
    QWEN_TEMPERATURE: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Temperature for randomness (0.0-2.0)"
    )
    QWEN_MAX_TOKENS: int = Field(
        default=1000,
        gt=0,
        description="Maximum tokens per request"
    )
    QWEN_TIMEOUT: int = Field(
        default=40,
        ge=5,
        le=120,
        description="Request timeout in seconds"
    )
    LLM_TEMPERATURE: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
        description="Unified temperature for diagram generation"
    )
    
    @field_validator('QWEN_API_URL')
    @classmethod
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError("API URL must start with http:// or https://")
        return v


class HunyuanAPISettings(BaseModel):
    """Tencent Hunyuan API configuration"""
    __category__ = "Tencent Hunyuan API"
    
    HUNYUAN_API_KEY: Optional[str] = Field(
        default="",
        description="Hunyuan secret key (optional)"
    )
    HUNYUAN_SECRET_ID: Optional[str] = Field(
        default="",
        description="Hunyuan secret ID (optional)"
    )
    HUNYUAN_API_URL: str = Field(
        default="https://hunyuan.tencentcloudapi.com",
        description="Hunyuan API URL"
    )
    HUNYUAN_MODEL: str = Field(
        default="hunyuan-turbo",
        description="Hunyuan model name"
    )
    HUNYUAN_TEMPERATURE: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Temperature (MUST be ≤ 2.0 for Hunyuan API)"
    )
    HUNYUAN_MAX_TOKENS: int = Field(
        default=2000,
        gt=0,
        description="Maximum tokens per request"
    )
    
    @field_validator('HUNYUAN_TEMPERATURE')
    @classmethod
    def validate_hunyuan_temperature(cls, v):
        """Hunyuan API requires temperature ≤ 2.0"""
        if v > 2.0:
            raise ValueError(f"Hunyuan temperature must be ≤ 2.0, got {v}")
        return v


class DashscopeRateLimitSettings(BaseModel):
    """Dashscope platform rate limiting configuration"""
    __category__ = "Dashscope Rate Limiting"
    
    DASHSCOPE_QPM_LIMIT: int = Field(
        default=200,
        gt=0,
        description="Queries per minute limit"
    )
    DASHSCOPE_CONCURRENT_LIMIT: int = Field(
        default=50,
        gt=0,
        description="Maximum concurrent requests"
    )
    DASHSCOPE_RATE_LIMITING_ENABLED: bool = Field(
        default=True,
        description="Enable/disable rate limiting"
    )


class GraphSettings(BaseModel):
    """Graph generation and styling settings"""
    __category__ = "Graph & UI Settings"
    
    GRAPH_LANGUAGE: GraphLanguage = Field(
        default=GraphLanguage.ZH,
        description="Language for graph generation (zh/en)"
    )
    TOPIC_FONT_SIZE: int = Field(
        default=18,
        gt=0,
        description="Topic node font size in pixels"
    )
    CHAR_FONT_SIZE: int = Field(
        default=14,
        gt=0,
        description="Characteristic node font size in pixels"
    )
    WATERMARK_TEXT: str = Field(
        default="MindGraph",
        description="Watermark text on generated graphs"
    )


class LoggingSettings(BaseModel):
    """Logging configuration"""
    __category__ = "Logging Configuration"
    
    LOG_LEVEL: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level"
    )
    VERBOSE_LOGGING: bool = Field(
        default=False,
        description="Enable verbose logging (logs all user interactions)"
    )


class FeatureFlagSettings(BaseModel):
    """Feature flags for experimental features"""
    __category__ = "Feature Flags"
    
    FEATURE_LEARNING_MODE: bool = Field(
        default=False,
        description="Enable Learning Mode button"
    )
    FEATURE_THINKGUIDE: bool = Field(
        default=False,
        description="Enable ThinkGuide button"
    )
    FEATURE_MINDMATE: bool = Field(
        default=False,
        description="Enable MindMate AI Assistant button"
    )
    FEATURE_VOICE_AGENT: bool = Field(
        default=False,
        description="Enable Voice Agent (Qwen Omni Realtime)"
    )


class DifySettings(BaseModel):
    """Dify AI assistant configuration"""
    __category__ = "Dify AI Assistant"
    
    DIFY_API_KEY: Optional[str] = Field(
        default="",
        description="Dify API key (optional)"
    )
    DIFY_API_URL: str = Field(
        default="http://101.42.231.179/v1",
        description="Dify API URL"
    )
    DIFY_TIMEOUT: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Request timeout in seconds"
    )
    AI_ASSISTANT_NAME: str = Field(
        default="MindMate AI",
        min_length=1,
        max_length=50,
        description="AI assistant display name"
    )


class DatabaseSettings(BaseModel):
    """Database configuration"""
    __category__ = "Database Configuration"
    
    DATABASE_URL: str = Field(
        default="sqlite:///./mindgraph.db",
        description="Database connection URL"
    )
    
    @field_validator('DATABASE_URL')
    @classmethod
    def validate_database_url(cls, v):
        """Ensure DATABASE_URL is a valid SQLAlchemy URL"""
        valid_prefixes = ['sqlite:///', 'postgresql://', 'mysql://', 'mariadb://']
        if not any(v.startswith(prefix) for prefix in valid_prefixes):
            raise ValueError(f"DATABASE_URL must start with one of: {valid_prefixes}")
        return v


class AuthSettings(BaseModel):
    """Authentication and security settings"""
    __category__ = "Authentication & Security"
    
    JWT_SECRET_KEY: str = Field(
        ...,
        min_length=32,
        description="JWT secret key (minimum 32 characters, CHANGE IN PRODUCTION!)"
    )
    JWT_EXPIRY_HOURS: int = Field(
        default=24,
        gt=0,
        le=168,  # Max 7 days
        description="JWT token expiry in hours"
    )
    AUTH_MODE: AuthMode = Field(
        default=AuthMode.STANDARD,
        description="Authentication mode (standard/enterprise/demo)"
    )
    ADMIN_PHONES: str = Field(
        default="",
        description="Admin phone numbers (comma-separated)"
    )
    ENTERPRISE_DEFAULT_ORG_CODE: Optional[str] = Field(
        default="DEMO-001",
        description="Default organization code for enterprise mode"
    )
    ENTERPRISE_DEFAULT_USER_PHONE: Optional[str] = Field(
        default="enterprise@system.com",
        description="Default user phone for enterprise mode"
    )
    DEMO_PASSKEY: Optional[str] = Field(
        default="888888",
        min_length=6,
        max_length=6,
        description="Demo mode passkey (6 digits)"
    )
    ADMIN_DEMO_PASSKEY: Optional[str] = Field(
        default="999999",
        min_length=6,
        max_length=6,
        description="Admin demo mode passkey (6 digits)"
    )
    INVITATION_CODES: str = Field(
        default="",
        description="Invitation codes (format: ORG:CODE:DATE,ORG2:CODE2:DATE2)"
    )
    
    @field_validator('DEMO_PASSKEY', 'ADMIN_DEMO_PASSKEY')
    @classmethod
    def validate_passkey(cls, v):
        """Validate passkey is 6 digits"""
        if v and (not v.isdigit() or len(v) != 6):
            raise ValueError("Passkey must be exactly 6 digits")
        return v
    
    @field_validator('JWT_SECRET_KEY')
    @classmethod
    def validate_jwt_secret(cls, v):
        """Warn if using default/weak JWT secret"""
        if len(v) < 32:
            raise ValueError("JWT secret must be at least 32 characters")
        if "change" in v.lower() or "secret" in v.lower() or "your-" in v.lower():
            # This is likely the default from env.example
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("JWT_SECRET_KEY appears to be default value - CHANGE IN PRODUCTION!")
        return v


# ============================================================================
# MASTER SETTINGS SCHEMA
# ============================================================================

class EnvSettingsSchema(BaseModel):
    """
    Complete environment settings schema.
    
    This combines all category models into a single validation schema.
    Used by EnvManager to validate the entire configuration at once.
    """
    app: AppSettings
    qwen: QwenAPISettings
    hunyuan: HunyuanAPISettings
    dashscope: DashscopeRateLimitSettings
    graph: GraphSettings
    logging: LoggingSettings
    features: FeatureFlagSettings
    dify: DifySettings
    database: DatabaseSettings
    auth: AuthSettings
    
    class Config:
        """Pydantic configuration"""
        use_enum_values = True  # Convert enums to their values
        json_schema_extra = {
            "example": {
                "app": {
                    "HOST": "0.0.0.0",
                    "PORT": 9527,
                    "DEBUG": False
                },
                "qwen": {
                    "QWEN_API_KEY": "sk-xxx",
                    "QWEN_MODEL_CLASSIFICATION": "qwen-turbo"
                }
                # ... more examples
            }
        }

