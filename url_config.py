"""
MindGraph URL Configuration
==========================

Centralized URL configuration for all endpoints in the MindGraph application.
This ensures consistency and makes it easy to update URLs across the application.

Version: 2.3.4
"""

# ============================================================================
# API ENDPOINTS
# ============================================================================

# Core Graph Generation
API_GENERATE_GRAPH = '/api/generate_graph'
API_GENERATE_PNG = '/api/generate_png'
API_GENERATE_GRAPH_DEEPSEEK = '/api/generate_graph_deepseek'
API_GENERATE_DEVELOPMENT_PROMPT = '/api/generate_development_prompt'
API_UPDATE_STYLE = '/api/update_style'

# ============================================================================
# WEB ROUTES
# ============================================================================

# Main Pages
WEB_INDEX = '/'
WEB_DEBUG = '/debug'
WEB_STYLE_DEMO = '/style-demo'
WEB_TEST_STYLE_MANAGER = '/test-style-manager'
WEB_TEST_PNG_GENERATION = '/test-png-generation'
WEB_SIMPLE_TEST = '/simple-test'

# ============================================================================
# STATIC RESOURCES
# ============================================================================

# JavaScript Files
STATIC_D3_RENDERERS = '/static/js/d3-renderers.js'
STATIC_STYLE_MANAGER = '/static/js/style-manager.js'

# CSS and External Resources
EXTERNAL_D3_CDN = 'https://cdn.jsdelivr.net/npm/d3@7'
EXTERNAL_GOOGLE_FONTS = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap'

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_api_urls():
    """Get all API endpoint URLs."""
    return {
        'generate_graph': API_GENERATE_GRAPH,
        'generate_png': API_GENERATE_PNG,
        'generate_graph_deepseek': API_GENERATE_GRAPH_DEEPSEEK,
        'generate_development_prompt': API_GENERATE_DEVELOPMENT_PROMPT,
        'update_style': API_UPDATE_STYLE
    }

def get_web_urls():
    """Get all web route URLs."""
    return {
        'index': WEB_INDEX,
        'debug': WEB_DEBUG,
        'style_demo': WEB_STYLE_DEMO,
        'test_style_manager': WEB_TEST_STYLE_MANAGER,
        'test_png_generation': WEB_TEST_PNG_GENERATION,
        'simple_test': WEB_SIMPLE_TEST
    }

def get_static_urls():
    """Get all static resource URLs."""
    return {
        'd3_renderers': STATIC_D3_RENDERERS,
        'style_manager': STATIC_STYLE_MANAGER,
        'd3_cdn': EXTERNAL_D3_CDN,
        'google_fonts': EXTERNAL_GOOGLE_FONTS
    }

def get_all_urls():
    """Get all URLs in the application."""
    return {
        'api': get_api_urls(),
        'web': get_web_urls(),
        'static': get_static_urls()
    }

