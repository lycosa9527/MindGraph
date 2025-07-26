"""
D3.js_Dify Configuration Module
==============================

Version: 2.0.0

This module provides centralized configuration management for the D3.js_Dify application.
It handles environment variable loading, validation, and provides a clean interface
for accessing configuration values throughout the application.

Features:
- Dynamic environment variable loading with .env support
- Property-based configuration access for real-time updates
- Comprehensive validation for required and optional settings
- Default values for all configuration options
- Support for both Qwen and DeepSeek LLM configurations
- D3.js visualization customization options

Environment Variables:
- QWEN_API_KEY: Required for core functionality
- DEEPSEEK_API_KEY: Optional for enhanced features
- See env.example for complete configuration options

Usage:
    from config import config
    api_key = config.QWEN_API_KEY
    is_valid = config.validate_qwen_config()
"""

from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class Config:
    """
    Centralized configuration management for D3.js_Dify application.
    
    This class provides property-based access to all configuration values,
    ensuring that environment variables are read dynamically on each access.
    This allows for configuration changes without application restart.
    
    Features:
    - Property-based configuration access
    - Environment variable validation
    - Default value management
    - Configuration summary generation
    - API request formatting
    """
    
    # ============================================================================
    # QWEN API CONFIGURATION (Required for core functionality)
    # ============================================================================
    
    @property
    def QWEN_API_KEY(self):
        """Qwen API key for AI-powered graph generation."""
        return os.environ.get('QWEN_API_KEY')
    
    @property
    def QWEN_API_URL(self):
        """Qwen API endpoint URL."""
        return os.environ.get('QWEN_API_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions')
    
    @property
    def QWEN_MODEL(self):
        """Qwen model name for API requests."""
        return os.environ.get('QWEN_MODEL', 'qwen-turbo')
    
    @property
    def QWEN_TEMPERATURE(self):
        """Qwen model temperature for response creativity (0.0-1.0)."""
        return float(os.environ.get('QWEN_TEMPERATURE', '0.7'))
    
    @property
    def QWEN_MAX_TOKENS(self):
        """Maximum tokens for Qwen API responses."""
        return int(os.environ.get('QWEN_MAX_TOKENS', '1000'))
    
    @property
    def QWEN_TIMEOUT(self):
        """Timeout for Qwen API requests in seconds."""
        return int(os.environ.get('QWEN_TIMEOUT', '40'))
    
    # ============================================================================
    # DEEPSEEK API CONFIGURATION (Optional for enhanced features)
    # ============================================================================
    
    @property
    def DEEPSEEK_API_KEY(self):
        """DeepSeek API key for enhanced AI features."""
        return os.environ.get('DEEPSEEK_API_KEY')
    
    @property
    def DEEPSEEK_API_URL(self):
        """DeepSeek API endpoint URL."""
        return os.environ.get('DEEPSEEK_API_URL', 'https://api.deepseek.com/v1/chat/completions')
    
    @property
    def DEEPSEEK_MODEL(self):
        """DeepSeek model name for API requests."""
        return os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat')
    
    @property
    def DEEPSEEK_TEMPERATURE(self):
        """DeepSeek model temperature for response creativity (0.0-1.0)."""
        return float(os.environ.get('DEEPSEEK_TEMPERATURE', '0.7'))
    
    @property
    def DEEPSEEK_MAX_TOKENS(self):
        """Maximum tokens for DeepSeek API responses."""
        return int(os.environ.get('DEEPSEEK_MAX_TOKENS', '2000'))
    
    @property
    def DEEPSEEK_TIMEOUT(self):
        """Timeout for DeepSeek API requests in seconds."""
        return int(os.environ.get('DEEPSEEK_TIMEOUT', '60'))
    
    # ============================================================================
    # FLASK APPLICATION CONFIGURATION
    # ============================================================================
    
    @property
    def HOST(self):
        """Flask application host address."""
        return os.environ.get('HOST', '0.0.0.0')
    
    @property
    def PORT(self):
        """Flask application port number."""
        return int(os.environ.get('PORT', '9527'))
    
    @property
    def DEBUG(self):
        """Flask debug mode setting."""
        return os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # ============================================================================
    # GRAPH LANGUAGE AND CONTENT SETTINGS
    # ============================================================================
    
    @property
    def GRAPH_LANGUAGE(self):
        """Language for graph generation (zh/en)."""
        return os.environ.get('GRAPH_LANGUAGE', 'zh')
    
    @property
    def WATERMARK_TEXT(self):
        """Watermark text displayed on generated graphs."""
        return os.environ.get('WATERMARK_TEXT', 'D3.js_Dify')
    
    # ============================================================================
    # D3.js VISUALIZATION CONFIGURATION
    # ============================================================================
    
    # Font size settings
    @property
    def TOPIC_FONT_SIZE(self):
        """Font size for topic nodes in pixels."""
        return int(os.environ.get('TOPIC_FONT_SIZE', '18'))
    
    @property
    def CHAR_FONT_SIZE(self):
        """Font size for characteristic nodes in pixels."""
        return int(os.environ.get('CHAR_FONT_SIZE', '14'))
    
    # D3.js rendering dimensions
    @property
    def D3_BASE_WIDTH(self):
        """Base width for D3.js visualizations in pixels."""
        return int(os.environ.get('D3_BASE_WIDTH', '700'))
    
    @property
    def D3_BASE_HEIGHT(self):
        """Base height for D3.js visualizations in pixels."""
        return int(os.environ.get('D3_BASE_HEIGHT', '500'))
    
    @property
    def D3_PADDING(self):
        """Padding around D3.js visualizations in pixels."""
        return int(os.environ.get('D3_PADDING', '40'))
    
    # ============================================================================
    # D3.js THEME COLOR CONFIGURATION
    # ============================================================================
    
    # Topic node colors
    @property
    def D3_TOPIC_FILL(self):
        """Fill color for topic nodes."""
        return os.environ.get('D3_TOPIC_FILL', '#4e79a7')
    
    @property
    def D3_TOPIC_TEXT(self):
        """Text color for topic nodes."""
        return os.environ.get('D3_TOPIC_TEXT', '#ffffff')
    
    @property
    def D3_TOPIC_STROKE(self):
        """Stroke color for topic nodes."""
        return os.environ.get('D3_TOPIC_STROKE', '#2c3e50')
    
    # Similarity node colors
    @property
    def D3_SIM_FILL(self):
        """Fill color for similarity nodes."""
        return os.environ.get('D3_SIM_FILL', '#a7c7e7')
    
    @property
    def D3_SIM_TEXT(self):
        """Text color for similarity nodes."""
        return os.environ.get('D3_SIM_TEXT', '#2c3e50')
    
    @property
    def D3_SIM_STROKE(self):
        """Stroke color for similarity nodes."""
        return os.environ.get('D3_SIM_STROKE', '#4e79a7')
    
    # Difference node colors
    @property
    def D3_DIFF_FILL(self):
        """Fill color for difference nodes."""
        return os.environ.get('D3_DIFF_FILL', '#f4f6fb')
    
    @property
    def D3_DIFF_TEXT(self):
        """Text color for difference nodes."""
        return os.environ.get('D3_DIFF_TEXT', '#2c3e50')
    
    @property
    def D3_DIFF_STROKE(self):
        """Stroke color for difference nodes."""
        return os.environ.get('D3_DIFF_STROKE', '#a7c7e7')
    
    # ============================================================================
    # CONFIGURATION VALIDATION METHODS
    # ============================================================================
    
    def validate_qwen_config(self) -> bool:
        """
        Validate Qwen API configuration.
        
        Returns:
            bool: True if Qwen configuration is valid, False otherwise
        """
        if not self.QWEN_API_KEY:
            return False
        
        # Validate API URL format
        if not self.QWEN_API_URL.startswith(('http://', 'https://')):
            return False
        
        # Validate numeric values
        try:
            if not (0 <= self.QWEN_TEMPERATURE <= 1):
                return False
            if self.QWEN_MAX_TOKENS <= 0:
                return False
            if self.QWEN_TIMEOUT <= 0:
                return False
        except (ValueError, TypeError):
            return False
        
        return True
    
    def validate_deepseek_config(self) -> bool:
        """
        Validate DeepSeek API configuration.
        
        Returns:
            bool: True if DeepSeek configuration is valid, False otherwise
        """
        if not self.DEEPSEEK_API_KEY:
            return False
        
        # Validate API URL format
        if not self.DEEPSEEK_API_URL.startswith(('http://', 'https://')):
            return False
        
        # Validate numeric values
        try:
            if not (0 <= self.DEEPSEEK_TEMPERATURE <= 1):
                return False
            if self.DEEPSEEK_MAX_TOKENS <= 0:
                return False
            if self.DEEPSEEK_TIMEOUT <= 0:
                return False
        except (ValueError, TypeError):
            return False
        
        return True
    
    def check_deepseek_availability(self) -> bool:
        """
        Check if DeepSeek API is available and configured.
        
        Returns:
            bool: True if DeepSeek is available, False otherwise
        """
        return bool(self.DEEPSEEK_API_KEY and self.validate_deepseek_config())
    
    def validate_numeric_config(self) -> bool:
        """
        Validate all numeric configuration values.
        
        Returns:
            bool: True if all numeric values are valid, False otherwise
        """
        try:
            # Validate port number
            if not (1 <= self.PORT <= 65535):
                return False
            
            # Validate font sizes
            if self.TOPIC_FONT_SIZE <= 0 or self.CHAR_FONT_SIZE <= 0:
                return False
            
            # Validate D3.js dimensions
            if (self.D3_BASE_WIDTH <= 0 or self.D3_BASE_HEIGHT <= 0 or 
                self.D3_PADDING < 0):
                return False
            
            # Validate timeouts and token limits
            if (self.QWEN_TIMEOUT <= 0 or self.QWEN_MAX_TOKENS <= 0 or
                self.DEEPSEEK_TIMEOUT <= 0 or self.DEEPSEEK_MAX_TOKENS <= 0):
                return False
            
            return True
        except (ValueError, TypeError):
            return False
    
    # ============================================================================
    # CONFIGURATION SUMMARY AND DISPLAY
    # ============================================================================
    
    def print_config_summary(self):
        """
        Print a comprehensive configuration summary.
        
        Displays:
        - Flask application settings
        - API configurations and availability
        - D3.js visualization settings
        - Theme and styling options
        """
        logger.info("📋 Configuration Summary:")
        logger.info(f"   Flask: {self.HOST}:{self.PORT} (Debug: {self.DEBUG})")
        logger.info(f"   Qwen: {self.QWEN_MODEL} at {self.QWEN_API_URL}")
        
        if self.check_deepseek_availability():
            logger.info(f"   DeepSeek: {self.DEEPSEEK_MODEL} at {self.DEEPSEEK_API_URL}")
        else:
            logger.info("   DeepSeek: deepseek-chat (❌ Not Available)")
        
        logger.info(f"   Language: {self.GRAPH_LANGUAGE}")
        logger.info(f"   Theme: {self.D3_TOPIC_FILL} / {self.D3_SIM_FILL} / {self.D3_DIFF_FILL}")
        logger.info(f"   Dimensions: {self.D3_BASE_WIDTH}x{self.D3_BASE_HEIGHT}px")
    
    # ============================================================================
    # API REQUEST FORMATTING METHODS
    # ============================================================================
    
    def get_qwen_headers(self) -> dict:
        """
        Get headers for Qwen API requests.
        
        Returns:
            dict: Headers dictionary for Qwen API requests
        """
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.QWEN_API_KEY}'
        }
    
    def get_qwen_data(self, prompt: str) -> dict:
        """
        Get request data for Qwen API calls.
        
        Args:
            prompt (str): The prompt to send to Qwen
            
        Returns:
            dict: Request data dictionary for Qwen API
        """
        return {
            'model': self.QWEN_MODEL,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': self.QWEN_TEMPERATURE,
            'max_tokens': self.QWEN_MAX_TOKENS
        }
    
    def get_deepseek_headers(self) -> dict:
        """
        Get headers for DeepSeek API requests.
        
        Returns:
            dict: Headers dictionary for DeepSeek API requests
        """
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.DEEPSEEK_API_KEY}'
        }
    
    def get_deepseek_data(self, prompt: str) -> dict:
        """
        Get request data for DeepSeek API calls.
        
        Args:
            prompt (str): The prompt to send to DeepSeek
            
        Returns:
            dict: Request data dictionary for DeepSeek API
        """
        return {
            'model': self.DEEPSEEK_MODEL,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': self.DEEPSEEK_TEMPERATURE,
            'max_tokens': self.DEEPSEEK_MAX_TOKENS
        }
    
    # ============================================================================
    # D3.js THEME AND DIMENSION HELPERS
    # ============================================================================
    
    def get_d3_theme(self) -> dict:
        """
        Get complete D3.js theme configuration.
        
        Returns:
            dict: Complete theme configuration for D3.js visualizations
        """
        return {
            'topic': {
                'fill': self.D3_TOPIC_FILL,
                'text': self.D3_TOPIC_TEXT,
                'stroke': self.D3_TOPIC_STROKE
            },
            'similarity': {
                'fill': self.D3_SIM_FILL,
                'text': self.D3_SIM_TEXT,
                'stroke': self.D3_SIM_STROKE
            },
            'difference': {
                'fill': self.D3_DIFF_FILL,
                'text': self.D3_DIFF_TEXT,
                'stroke': self.D3_DIFF_STROKE
            }
        }
    
    def get_d3_dimensions(self) -> dict:
        """
        Get D3.js visualization dimensions.
        
        Returns:
            dict: Dimension configuration for D3.js visualizations
        """
        return {
            'width': self.D3_BASE_WIDTH,
            'height': self.D3_BASE_HEIGHT,
            'padding': self.D3_PADDING,
            'topicFontSize': self.TOPIC_FONT_SIZE,
            'charFontSize': self.CHAR_FONT_SIZE
        }

# Create global configuration instance
config = Config() 