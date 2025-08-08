from flask import Blueprint, render_template
import logging
from url_config import get_web_urls

web = Blueprint('web', __name__)
logger = logging.getLogger(__name__)

# Get URL configuration
URLS = get_web_urls()

@web.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"/ route failed: {e}", exc_info=True)
        return "An unexpected error occurred. Please try again later.", 500

@web.route('/debug')
def debug():
    try:
        return render_template('debug.html')
    except Exception as e:
        logger.error(f"/debug route failed: {e}", exc_info=True)
        return "An unexpected error occurred. Please try again later.", 500

@web.route('/style-demo')
def style_demo():
    try:
        return render_template('style-demo.html')
    except Exception as e:
        logger.error(f"/style-demo route failed: {e}", exc_info=True)
        return "An unexpected error occurred. Please try again later.", 500

@web.route('/test-style-manager')
def test_style_manager():
    try:
        return render_template('test_style_manager.html')
    except Exception as e:
        logger.error(f"/test-style-manager route failed: {e}", exc_info=True)
        return "An unexpected error occurred. Please try again later.", 500

@web.route('/test-png-generation')
def test_png_generation():
    try:
        return render_template('test_png_generation.html')
    except Exception as e:
        logger.error(f"/test-png-generation route failed: {e}", exc_info=True)
        return "An unexpected error occurred. Please try again later.", 500

@web.route('/simple-test')
def simple_test():
    try:
        return render_template('simple_test.html')
    except Exception as e:
        logger.error(f"/simple-test route failed: {e}", exc_info=True)
        return "An unexpected error occurred. Please try again later.", 500

@web.route('/browser-test')
def browser_test():
    try:
        return render_template('test_browser_rendering.html')
    except Exception as e:
        logger.error(f"/browser-test route failed: {e}", exc_info=True)
        return "An unexpected error occurred. Please try again later.", 500

@web.route('/bubble-map-test')
def bubble_map_test():
    try:
        return render_template('test_bubble_map_styling.html')
    except Exception as e:
        logger.error(f"/bubble-map-test route failed: {e}", exc_info=True)
        return "An unexpected error occurred. Please try again later.", 500









@web.route('/debug-theme-conversion')
def debug_theme_conversion():
    try:
        return render_template('debug_theme_conversion.html')
    except Exception as e:
        logger.error(f"/debug-theme-conversion route failed: {e}", exc_info=True)
        return "An unexpected error occurred. Please try again later.", 500

@web.route('/simple-theme-test')
def simple_theme_test():
    try:
        return render_template('simple_theme_test.html')
    except Exception as e:
        logger.error(f"/simple-theme-test route failed: {e}", exc_info=True)
        return "An unexpected error occurred. Please try again later.", 500

@web.route('/timing-stats')
def timing_stats():
    try:
        return render_template('timing_stats.html')
    except Exception as e:
        logger.error(f"/timing-stats route failed: {e}", exc_info=True)
        return "An unexpected error occurred. Please try again later.", 500

 