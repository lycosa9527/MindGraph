"""
MindGraph Configuration Module
==============================

Version: 2.3.1

This module provides centralized configuration management for the MindGraph application.
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
    Centralized configuration management for MindGraph application.
    Now with caching and validation to prevent race conditions and ensure consistent values.
    """
    def __init__(self):
        self._cache = {}
        self._cache_timestamp = 0
        self._cache_duration = 30  # Cache for 30 seconds
    def _get_cached_value(self, key: str, default=None):
        import time
        current_time = time.time()
        if current_time - self._cache_timestamp > self._cache_duration:
            self._cache.clear()
            self._cache_timestamp = current_time
        if key not in self._cache:
            self._cache[key] = os.environ.get(key, default)
        return self._cache[key]
    @property
    def QWEN_API_KEY(self):
        api_key = self._get_cached_value('QWEN_API_KEY')
        if not api_key or not isinstance(api_key, str):
            logger.warning("Invalid or missing QWEN_API_KEY")
            return None
        return api_key.strip()
    @property
    def QWEN_API_URL(self):
        return self._get_cached_value('QWEN_API_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions')
    @property
    def QWEN_MODEL(self):
        return self._get_cached_value('QWEN_MODEL', 'qwen-turbo')
    @property
    def QWEN_TEMPERATURE(self):
        try:
            temp = float(self._get_cached_value('QWEN_TEMPERATURE', '0.7'))
            if not 0.0 <= temp <= 1.0:
                logger.warning(f"Temperature {temp} out of range [0.0, 1.0], using 0.7")
                return 0.7
            return temp
        except (ValueError, TypeError):
            logger.warning("Invalid temperature value, using 0.7")
            return 0.7
    @property
    def QWEN_MAX_TOKENS(self):
        try:
            val = int(self._get_cached_value('QWEN_MAX_TOKENS', '1000'))
            if val < 100 or val > 4096:
                logger.warning(f"QWEN_MAX_TOKENS {val} out of range, using 1000")
                return 1000
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid QWEN_MAX_TOKENS value, using 1000")
            return 1000
    @property
    def QWEN_TIMEOUT(self):
        try:
            val = int(self._get_cached_value('QWEN_TIMEOUT', '40'))
            if val < 5 or val > 120:
                logger.warning(f"QWEN_TIMEOUT {val} out of range, using 40")
                return 40
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid QWEN_TIMEOUT value, using 40")
            return 40
    @property
    def DEEPSEEK_API_KEY(self):
        return self._get_cached_value('DEEPSEEK_API_KEY')
    @property
    def DEEPSEEK_API_URL(self):
        return self._get_cached_value('DEEPSEEK_API_URL', 'https://api.deepseek.com/v1/chat/completions')
    @property
    def DEEPSEEK_MODEL(self):
        """DeepSeek model name for API requests."""
        return self._get_cached_value('DEEPSEEK_MODEL', 'deepseek-chat')
    @property
    def DEEPSEEK_TEMPERATURE(self):
        """DeepSeek model temperature for response creativity (0.0-1.0)."""
        try:
            temp = float(self._get_cached_value('DEEPSEEK_TEMPERATURE', '0.7'))
            if not 0.0 <= temp <= 1.0:
                logger.warning(f"DeepSeek Temperature {temp} out of range [0.0, 1.0], using 0.7")
                return 0.7
            return temp
        except (ValueError, TypeError):
            logger.warning("Invalid DeepSeek Temperature value, using 0.7")
            return 0.7
    @property
    def DEEPSEEK_MAX_TOKENS(self):
        """Maximum tokens for DeepSeek API responses."""
        try:
            val = int(self._get_cached_value('DEEPSEEK_MAX_TOKENS', '2000'))
            if val < 100 or val > 4096:
                logger.warning(f"DeepSeek MAX_TOKENS {val} out of range, using 2000")
                return 2000
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid DeepSeek MAX_TOKENS value, using 2000")
            return 2000
    @property
    def DEEPSEEK_TIMEOUT(self):
        """Timeout for DeepSeek API requests in seconds."""
        try:
            val = int(self._get_cached_value('DEEPSEEK_TIMEOUT', '60'))
            if val < 5 or val > 120:
                logger.warning(f"DeepSeek TIMEOUT {val} out of range, using 60")
                return 60
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid DeepSeek TIMEOUT value, using 60")
            return 60
    @property
    def HOST(self):
        """Flask application host address."""
        return self._get_cached_value('HOST', '0.0.0.0')
    
    @property
    def PORT(self):
        """Flask application port number."""
        try:
            val = int(self._get_cached_value('PORT', '9527'))
            if not (1 <= val <= 65535):
                logger.warning(f"PORT {val} out of range, using 9527")
                return 9527
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid PORT value, using 9527")
            return 9527
    
    @property
    def DEBUG(self):
        """Flask debug mode setting."""
        return self._get_cached_value('DEBUG', 'False').lower() == 'true'
    
    # ============================================================================
    # GRAPH LANGUAGE AND CONTENT SETTINGS
    # ============================================================================
    
    @property
    def GRAPH_LANGUAGE(self):
        """Language for graph generation (zh/en)."""
        return self._get_cached_value('GRAPH_LANGUAGE', 'zh')
    
    @property
    def WATERMARK_TEXT(self):
        """Watermark text displayed on generated graphs."""
        return self._get_cached_value('WATERMARK_TEXT', 'MindGraph')
    
    # ============================================================================
    # D3.js VISUALIZATION CONFIGURATION
    # ============================================================================
    
    # Font size settings
    @property
    def TOPIC_FONT_SIZE(self):
        """Font size for topic nodes in pixels."""
        try:
            val = int(self._get_cached_value('TOPIC_FONT_SIZE', '18'))
            if val <= 0:
                logger.warning(f"TOPIC_FONT_SIZE {val} out of range, using 18")
                return 18
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid TOPIC_FONT_SIZE value, using 18")
            return 18
    
    @property
    def CHAR_FONT_SIZE(self):
        """Font size for characteristic nodes in pixels."""
        try:
            val = int(self._get_cached_value('CHAR_FONT_SIZE', '14'))
            if val <= 0:
                logger.warning(f"CHAR_FONT_SIZE {val} out of range, using 14")
                return 14
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid CHAR_FONT_SIZE value, using 14")
            return 14
    
    # D3.js rendering dimensions
    @property
    def D3_BASE_WIDTH(self):
        """Base width for D3.js visualizations in pixels."""
        try:
            val = int(self._get_cached_value('D3_BASE_WIDTH', '700'))
            if val <= 0:
                logger.warning(f"D3_BASE_WIDTH {val} out of range, using 700")
                return 700
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid D3_BASE_WIDTH value, using 700")
            return 700
    
    @property
    def D3_BASE_HEIGHT(self):
        """Base height for D3.js visualizations in pixels."""
        try:
            val = int(self._get_cached_value('D3_BASE_HEIGHT', '500'))
            if val <= 0:
                logger.warning(f"D3_BASE_HEIGHT {val} out of range, using 500")
                return 500
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid D3_BASE_HEIGHT value, using 500")
            return 500
    
    @property
    def D3_PADDING(self):
        """Padding around D3.js visualizations in pixels."""
        try:
            val = int(self._get_cached_value('D3_PADDING', '40'))
            if val < 0:
                logger.warning(f"D3_PADDING {val} out of range, using 40")
                return 40
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid D3_PADDING value, using 40")
            return 40
    
    # ============================================================================
    # D3.js THEME COLOR CONFIGURATION
    # ============================================================================
    
    # Topic node colors
    @property
    def D3_TOPIC_FILL(self):
        """Fill color for topic nodes."""
        return self._get_cached_value('D3_TOPIC_FILL', '#4e79a7')
    
    @property
    def D3_TOPIC_TEXT(self):
        """Text color for topic nodes."""
        return self._get_cached_value('D3_TOPIC_TEXT', '#ffffff')
    
    @property
    def D3_TOPIC_STROKE(self):
        """Stroke color for topic nodes."""
        return self._get_cached_value('D3_TOPIC_STROKE', '#2c3e50')
    
    # Similarity node colors
    @property
    def D3_SIM_FILL(self):
        """Fill color for similarity nodes."""
        return self._get_cached_value('D3_SIM_FILL', '#a7c7e7')
    
    @property
    def D3_SIM_TEXT(self):
        """Text color for similarity nodes."""
        return self._get_cached_value('D3_SIM_TEXT', '#2c3e50')
    
    @property
    def D3_SIM_STROKE(self):
        """Stroke color for similarity nodes."""
        return self._get_cached_value('D3_SIM_STROKE', '#4e79a7')
    
    # Difference node colors
    @property
    def D3_DIFF_FILL(self):
        """Fill color for difference nodes."""
        return self._get_cached_value('D3_DIFF_FILL', '#f4f6fb')
    
    @property
    def D3_DIFF_TEXT(self):
        """Text color for difference nodes."""
        return self._get_cached_value('D3_DIFF_TEXT', '#2c3e50')
    
    @property
    def D3_DIFF_STROKE(self):
        """Stroke color for difference nodes."""
        return self._get_cached_value('D3_DIFF_STROKE', '#a7c7e7')
    
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
    
    def get_watermark_config(self) -> dict:
        """
        Get watermark configuration.
        
        Returns:
            dict: Watermark configuration for D3.js visualizations
        """
        return {
            'watermarkText': self.WATERMARK_TEXT
        }

# Create global configuration instance
config = Config() 