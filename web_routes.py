from flask import Blueprint, render_template
import logging

web = Blueprint('web', __name__)
logger = logging.getLogger(__name__)

@web.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"/ route failed: {e}", exc_info=True)
        return "An unexpected error occurred. Please try again later.", 500

@web.route('/demo')
def demo():
    try:
        return render_template('demo.html')
    except Exception as e:
        logger.error(f"/demo route failed: {e}", exc_info=True)
        return "An unexpected error occurred. Please try again later.", 500 