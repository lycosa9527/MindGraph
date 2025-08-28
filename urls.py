"""
MindGraph URL Configuration
==========================

Centralized URL configuration for all endpoints in the MindGraph application.
This ensures consistency and makes it easy to update URLs across the application.

Version: 2.4.0
"""

# ============================================================================
# API ENDPOINTS
# ============================================================================

# Core Graph Generation
API_GENERATE_GRAPH = '/api/generate_graph'
API_GENERATE_PNG = '/api/generate_png'
API_GENERATE_DINGTALK = '/api/generate_dingtalk'
API_UPDATE_STYLE = '/api/update_style'
API_TEMP_IMAGES = '/api/temp_images'

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
WEB_BROWSER_TEST = '/browser-test'
WEB_BUBBLE_MAP_TEST = '/bubble-map-test'
WEB_DEBUG_THEME_CONVERSION = '/debug-theme-conversion'
WEB_SIMPLE_THEME_TEST = '/simple-theme-test'
WEB_TIMING_STATS = '/timing-stats'

# ============================================================================
# STATIC RESOURCES
# ============================================================================

# Static file paths
STATIC_CSS = '/static/css'
STATIC_JS = '/static/js'
STATIC_IMAGES = '/static/images'
# REMOVED: STATIC_D3_RENDERERS = '/static/js/d3-renderers.js' - No longer needed
STATIC_STYLE_MANAGER = '/static/js/style-manager.js'

# CSS and External Resources
EXTERNAL_D3_CDN = '/static/js/d3.min.js'  # Now points to local D3.js
EXTERNAL_GOOGLE_FONTS = '/static/fonts/inter.css'  # Now points to local Inter font CSS

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_api_urls():
    """Get all API endpoint URLs."""
    return {
        'generate_graph': API_GENERATE_GRAPH,
        'generate_png': API_GENERATE_PNG,
        'generate_dingtalk': API_GENERATE_DINGTALK,
        'update_style': API_UPDATE_STYLE,
        'temp_images': API_TEMP_IMAGES
    }

def get_web_urls():
    """Get all web route URLs."""
    return {
        'index': WEB_INDEX,
        'debug': WEB_DEBUG,
        'style_demo': WEB_STYLE_DEMO,
        'test_style_manager': WEB_TEST_STYLE_MANAGER,
        'test_png_generation': WEB_TEST_PNG_GENERATION,
        'simple_test': WEB_SIMPLE_TEST,
        'browser_test': WEB_BROWSER_TEST,
        'bubble_map_test': WEB_BUBBLE_MAP_TEST,
        'debug_theme_conversion': WEB_DEBUG_THEME_CONVERSION,
        'simple_theme_test': WEB_SIMPLE_THEME_TEST,
        'timing_stats': WEB_TIMING_STATS
    }

def get_static_urls():
    """Get all static resource URLs."""
    return {
        'css': STATIC_CSS,
        'js': STATIC_JS,
        'images': STATIC_IMAGES,
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

