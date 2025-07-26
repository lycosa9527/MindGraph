import os
from typing import Optional

class Config:
    """Centralized configuration for D3.js Graph Application"""
    # QWEN API CONFIGURATION
    QWEN_API_KEY: str = os.environ.get('QWEN_API_KEY')  # No default, must be set in environment
    QWEN_API_URL: str = os.environ.get('QWEN_API_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions')
    QWEN_MODEL: str = os.environ.get('QWEN_MODEL', 'qwen-turbo')
    QWEN_TEMPERATURE: float = float(os.environ.get('QWEN_TEMPERATURE', '0.7'))
    QWEN_MAX_TOKENS: int = int(os.environ.get('QWEN_MAX_TOKENS', '1000'))
    QWEN_TIMEOUT: int = int(os.environ.get('QWEN_TIMEOUT', '40'))  # Timeout in seconds for LLM operations
    # FLASK APPLICATION CONFIGURATION
    HOST: str = os.environ.get('HOST', '0.0.0.0')
    PORT: int = int(os.environ.get('PORT', '9527'))
    DEBUG: bool = os.environ.get('DEBUG', 'False').lower() == 'true'
    # GRAPH LANGUAGE SETTINGS
    GRAPH_LANGUAGE: str = os.environ.get('GRAPH_LANGUAGE', 'zh')
    # UI/Graph Styling (optional, for D3.js)
    TOPIC_FONT_SIZE: int = int(os.environ.get('TOPIC_FONT_SIZE', '18'))
    CHAR_FONT_SIZE: int = int(os.environ.get('CHAR_FONT_SIZE', '14'))
    
    # D3.js Rendering Configuration
    D3_BASE_WIDTH: int = int(os.environ.get('D3_BASE_WIDTH', '700'))
    D3_BASE_HEIGHT: int = int(os.environ.get('D3_BASE_HEIGHT', '500'))
    D3_PADDING: int = int(os.environ.get('D3_PADDING', '40'))
    
    # D3.js Theme Colors
    D3_TOPIC_FILL: str = os.environ.get('D3_TOPIC_FILL', '#4e79a7')
    D3_TOPIC_TEXT: str = os.environ.get('D3_TOPIC_TEXT', '#ffffff')
    D3_TOPIC_STROKE: str = os.environ.get('D3_TOPIC_STROKE', '#35506b')
    D3_SIM_FILL: str = os.environ.get('D3_SIM_FILL', '#a7c7e7')
    D3_SIM_TEXT: str = os.environ.get('D3_SIM_TEXT', '#333333')
    D3_SIM_STROKE: str = os.environ.get('D3_SIM_STROKE', '#4e79a7')
    D3_DIFF_FILL: str = os.environ.get('D3_DIFF_FILL', '#f4f6fb')
    D3_DIFF_TEXT: str = os.environ.get('D3_DIFF_TEXT', '#4e79a7')
    D3_DIFF_STROKE: str = os.environ.get('D3_DIFF_STROKE', '#4e79a7')
    
    # Watermark (optional, for D3.js SVG export)
    WATERMARK_TEXT: str = os.environ.get('WATERMARK_TEXT', 'MindSpring')
    # Validation and summary methods remain, but remove references to Docker, Export, and Image config
    @classmethod
    def validate_qwen_config(cls) -> bool:
        if not cls.QWEN_API_KEY:
            print("QWEN_API_KEY environment variable is required")
            print("Set QWEN_API_KEY in your .env file or environment")
            return False
        if not cls.QWEN_API_URL or cls.QWEN_API_URL == '':
            print("QWEN_API_URL is not set")
            return False
        if not cls.QWEN_API_URL.startswith(('http://', 'https://')):
            print("QWEN_API_URL must be a valid HTTP/HTTPS URL")
            return False
        print("Qwen API configuration is valid")
        return True
    
    @classmethod
    def validate_numeric_config(cls) -> bool:
        """Validate numeric configuration values."""
        try:
            # Validate port range
            if not (1024 <= cls.PORT <= 65535):
                print(f"PORT must be between 1024 and 65535, got {cls.PORT}")
                return False
            
            # Validate temperature range
            if not (0.0 <= cls.QWEN_TEMPERATURE <= 2.0):
                print(f"QWEN_TEMPERATURE must be between 0.0 and 2.0, got {cls.QWEN_TEMPERATURE}")
                return False
            
            # Validate max tokens
            if not (1 <= cls.QWEN_MAX_TOKENS <= 4000):
                print(f"QWEN_MAX_TOKENS must be between 1 and 4000, got {cls.QWEN_MAX_TOKENS}")
                return False
            
            # Validate timeout
            if not (5 <= cls.QWEN_TIMEOUT <= 300):  # Between 5 seconds and 5 minutes
                print(f"QWEN_TIMEOUT must be between 5 and 300 seconds, got {cls.QWEN_TIMEOUT}")
                return False
            
            # Validate font sizes
            if not (8 <= cls.TOPIC_FONT_SIZE <= 72):
                print(f"TOPIC_FONT_SIZE must be between 8 and 72, got {cls.TOPIC_FONT_SIZE}")
                return False
            
            if not (8 <= cls.CHAR_FONT_SIZE <= 48):
                print(f"CHAR_FONT_SIZE must be between 8 and 48, got {cls.CHAR_FONT_SIZE}")
                return False
            
            # Validate D3.js dimensions
            if not (100 <= cls.D3_BASE_WIDTH <= 2000):
                print(f"D3_BASE_WIDTH must be between 100 and 2000, got {cls.D3_BASE_WIDTH}")
                return False
            
            if not (100 <= cls.D3_BASE_HEIGHT <= 2000):
                print(f"D3_BASE_HEIGHT must be between 100 and 2000, got {cls.D3_BASE_HEIGHT}")
                return False
            
            if not (10 <= cls.D3_PADDING <= 200):
                print(f"D3_PADDING must be between 10 and 200, got {cls.D3_PADDING}")
                return False
            
            # Validate color formats (accept both 3 and 6 character hex colors)
            color_pattern = r'^#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?$'
            import re
            for color_name, color_value in [
                ('D3_TOPIC_FILL', cls.D3_TOPIC_FILL),
                ('D3_TOPIC_TEXT', cls.D3_TOPIC_TEXT),
                ('D3_TOPIC_STROKE', cls.D3_TOPIC_STROKE),
                ('D3_SIM_FILL', cls.D3_SIM_FILL),
                ('D3_SIM_TEXT', cls.D3_SIM_TEXT),
                ('D3_SIM_STROKE', cls.D3_SIM_STROKE),
                ('D3_DIFF_FILL', cls.D3_DIFF_FILL),
                ('D3_DIFF_TEXT', cls.D3_DIFF_TEXT),
                ('D3_DIFF_STROKE', cls.D3_DIFF_STROKE),
            ]:
                if not re.match(color_pattern, color_value):
                    print(f"{color_name} must be a valid hex color (e.g., #4e79a7 or #fff), got {color_value}")
                    return False
            
            return True
        except Exception as e:
            print(f"Configuration validation error: {e}")
            return False
    @classmethod
    def print_config_summary(cls):
        print("\n" + "="*80)
        print("D3.js GRAPH APP CONFIGURATION SUMMARY")
        print("="*80)
        print(f"Flask App: {cls.HOST}:{cls.PORT} (Debug: {cls.DEBUG})")
        print(f"Qwen API: {cls.QWEN_API_URL}")
        print(f"Qwen Model: {cls.QWEN_MODEL}")
        print(f"Graph Language: {cls.GRAPH_LANGUAGE}")
        print(f"Watermark: {cls.WATERMARK_TEXT}")
        print(f"Font Sizes: Topics {cls.TOPIC_FONT_SIZE}px, Characteristics {cls.CHAR_FONT_SIZE}px")
        print(f"D3.js Dimensions: {cls.D3_BASE_WIDTH}x{cls.D3_BASE_HEIGHT} (padding: {cls.D3_PADDING})")
        print(f"D3.js Theme: Topic={cls.D3_TOPIC_FILL}, Similarities={cls.D3_SIM_FILL}, Differences={cls.D3_DIFF_FILL}")
        print("="*80 + "\n")
    @classmethod
    def get_qwen_headers(cls) -> dict:
        return {
            "Authorization": f"Bearer {cls.QWEN_API_KEY}",
            "Content-Type": "application/json"
        }
    @classmethod
    def get_qwen_data(cls, prompt: str) -> dict:
        return {
            "model": cls.QWEN_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": cls.QWEN_TEMPERATURE,
            "max_tokens": cls.QWEN_MAX_TOKENS
        }
    
    @classmethod
    def get_d3_theme(cls) -> dict:
        """Get D3.js theme configuration."""
        return {
            "topicFill": cls.D3_TOPIC_FILL,
            "topicText": cls.D3_TOPIC_TEXT,
            "topicStroke": cls.D3_TOPIC_STROKE,
            "topicStrokeWidth": 3,
            "simFill": cls.D3_SIM_FILL,
            "simText": cls.D3_SIM_TEXT,
            "simStroke": cls.D3_SIM_STROKE,
            "simStrokeWidth": 2,
            "diffFill": cls.D3_DIFF_FILL,
            "diffText": cls.D3_DIFF_TEXT,
            "diffStroke": cls.D3_DIFF_STROKE,
            "diffStrokeWidth": 2,
            "fontTopic": cls.TOPIC_FONT_SIZE,
            "fontSim": cls.CHAR_FONT_SIZE,
            "fontDiff": cls.CHAR_FONT_SIZE - 1
        }
    
    @classmethod
    def get_d3_dimensions(cls) -> dict:
        """Get D3.js rendering dimensions."""
        return {
            "baseWidth": cls.D3_BASE_WIDTH,
            "baseHeight": cls.D3_BASE_HEIGHT,
            "padding": cls.D3_PADDING
        }

# Create a global config instance
config = Config() 