from flask import Blueprint, render_template
import logging
import os
from functools import wraps
from dotenv import load_dotenv
from urls import (
    WEB_INDEX, WEB_DEBUG, WEB_STYLE_DEMO, WEB_TEST_STYLE_MANAGER,
    WEB_TEST_PNG_GENERATION, WEB_SIMPLE_TEST, WEB_BROWSER_TEST,
    WEB_BUBBLE_MAP_TEST, WEB_DEBUG_THEME_CONVERSION, WEB_SIMPLE_THEME_TEST,
    WEB_TIMING_STATS
)

# Load environment variables for logging configuration
load_dotenv()

web = Blueprint('web', __name__)

# Configure logger with environment variable support
logger = logging.getLogger(__name__)
log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_str, logging.INFO)
logger.setLevel(log_level)


def handle_template_errors(template_name):
    """Decorator to handle template rendering errors consistently."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return render_template(template_name)
            except Exception as e:
                route_path = func.__name__.replace('_', '-')
                logger.error(f"/{route_path} route failed: {e}", exc_info=True)
                return "An unexpected error occurred. Please try again later.", 500
        return wrapper
    return decorator


@web.route(WEB_INDEX)
@handle_template_errors('index.html')
def index():
    pass


@web.route(WEB_DEBUG)
@handle_template_errors('debug.html')
def debug():
    pass


@web.route(WEB_STYLE_DEMO)
@handle_template_errors('style-demo.html')
def style_demo():
    pass


@web.route(WEB_TEST_STYLE_MANAGER)
@handle_template_errors('test_style_manager.html')
def test_style_manager():
    pass


@web.route(WEB_TEST_PNG_GENERATION)
@handle_template_errors('test_png_generation.html')
def test_png_generation():
    pass


@web.route(WEB_SIMPLE_TEST)
@handle_template_errors('simple_test.html')
def simple_test():
    pass


@web.route(WEB_BROWSER_TEST)
@handle_template_errors('test_browser_rendering.html')
def browser_test():
    pass


@web.route(WEB_BUBBLE_MAP_TEST)
@handle_template_errors('test_bubble_map_styling.html')
def bubble_map_test():
    pass


@web.route(WEB_DEBUG_THEME_CONVERSION)
@handle_template_errors('debug_theme_conversion.html')
def debug_theme_conversion():
    pass


@web.route(WEB_SIMPLE_THEME_TEST)
@handle_template_errors('simple_theme_test.html')
def simple_theme_test():
    pass


@web.route(WEB_TIMING_STATS)
@handle_template_errors('timing_stats.html')
def timing_stats():
    pass