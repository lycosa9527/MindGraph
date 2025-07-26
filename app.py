from flask import Flask, request, jsonify, render_template, send_file
import agent
import graph_specs
import logging
import time
from config import config
import os
import socket
import webbrowser
import threading
import shutil
import sys
from dotenv import load_dotenv
load_dotenv()
import tempfile
import asyncio
import base64
import subprocess
from werkzeug.exceptions import HTTPException
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from api_routes import api
from web_routes import web
from pathlib import Path

# Create logs directory
os.makedirs("logs", exist_ok=True)

# Simple logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/app.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# Import dependency checker module
import dependency_checker.check_dependencies as dep_checker

# Ensure Playwright browsers are installed (for new users)
def ensure_playwright_browsers():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # Try to launch Chrome to check if installed
            browser = p.chromium.launch(headless=True)
            browser.close()
    except Exception:
        logger.info("Playwright Chrome browser not found. Installing Chrome browser...")
        subprocess.run([sys.executable, '-m', 'playwright', 'install', 'chromium'], check=True)

ensure_playwright_browsers()

# =========================================================================
# CONFIGURATION - Now centralized in config.py
# =========================================================================
# All configuration is now handled by the config module
# Environment variables can override defaults
# =========================================================================

app = Flask(__name__)

# Simple request logging
@app.before_request
def log_request():
    """Log incoming requests."""
    request.start_time = time.time()
    logger.info(f"Request: {request.method} {request.path} from {request.remote_addr}")

@app.after_request
def log_response(response):
    """Log response details."""
    if hasattr(request, 'start_time'):
        response_time = time.time() - request.start_time
        logger.info(f"Response: {response.status_code} in {response_time:.3f}s")
        
        # Log slow requests with different thresholds
        if 'generate_png' in request.path and response_time > 20:
            logger.warning(f"Slow PNG generation: {request.method} {request.path} took {response_time:.3f}s")
        elif response_time > 5:
            logger.warning(f"Slow request: {request.method} {request.path} took {response_time:.3f}s")
            # Debug: Log the actual path for PNG-related requests
            if 'png' in request.path.lower() or 'generate' in request.path.lower():
                logger.info(f"DEBUG: PNG-related request path: {request.path}")
    
    return response

# Configure CORS based on environment
if config.DEBUG:
    # In development, allow all origins but with some restrictions
    CORS(app, origins=['http://localhost:9527', 'http://127.0.0.1:9527', 'http://localhost:3000'])
else:
    # In production, restrict to specific origins
    CORS(app, origins=[
        'http://localhost:9527',
        'http://127.0.0.1:9527'
        # Add your actual production domains here
    ])
limiter = Limiter(get_remote_address, app=app, default_limits=["20 per minute"])

app.register_blueprint(api)
app.register_blueprint(web)



# Simple status endpoint
@app.route('/status')
def get_status():
    """Get basic application status."""
    import psutil
    
    memory = psutil.virtual_memory()
    uptime = time.time() - app.start_time if hasattr(app, 'start_time') else 0
    
    status_data = {
        'status': 'running',
        'uptime_seconds': round(uptime, 1),
        'memory_percent': round(memory.percent, 1),
        'timestamp': time.time()
    }
    
    logger.info(f"Status check: OK")
    return jsonify(status_data), 200

# Print ASCII banner at startup

# Global error handler
@app.errorhandler(Exception)
def handle_exception(e):
    # Pass through HTTP errors
    if isinstance(e, HTTPException):
        logger.warning(f"HTTP {e.code}: {e.description}")
        return jsonify({'error': e.description}), e.code
    
    # Log unhandled exceptions
    logger.error(f"Unhandled exception: {type(e).__name__}: {e}", exc_info=True)
    
    # Return simple error response
    error_response = {'error': 'An unexpected error occurred. Please try again later.'}
    
    # Add debug info in debug mode
    if config.DEBUG:
        error_response['debug'] = str(e)
    
    return jsonify(error_response), 500

def get_local_ip():
    """Get the local IP address.
    """
    try:
        # Connect to a remote address to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

def open_browser_demo(host, port):
    """Open the demo page with proper server readiness check."""
    try:
        # Determine the correct URL
        if host == '0.0.0.0':
            url = f"http://localhost:{port}/demo"
        else:
            url = f"http://{host}:{port}/demo"
        
        def open_browser():
            import requests
            max_attempts = 15
            for attempt in range(max_attempts):
                try:
                    # Try to connect to the status endpoint
                    response = requests.get(f"http://localhost:{port}/status", timeout=2)
                    if response.status_code == 200:
                        webbrowser.open(url)
                        return True  # Success
                except requests.exceptions.RequestException:
                    pass
                
                time.sleep(2)
            
            # Don't open browser if server didn't respond
            logger.warning("Server not ready, skipping browser opening")
            return False
        
        # Start browser opening in a separate thread
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()
        
    except Exception as e:
        logger.warning(f"Could not open browser automatically: {e}")

def print_banner(host, port):
    """Print ASCII art banner and application info."""
    banner = """
================================================================================
    ███╗   ███╗██╗███╗   ██╗██████╗ ███╗   ███╗ █████╗ ████████╗███████╗
    ████╗ ████║██║████╗  ██║██╔══██╗████╗ ████║██╔══██╗╚══██╔══╝██╔════╝
    ██╔████╔██║██║██╔██╗ ██║██║  ██║██╔████╔██║███████║   ██║   █████╗  
    ██║╚██╔╝██║██║██║╚██╗██║██║  ██║██║╚██╔╝██║██╔══██║   ██║   ██╔══╝  
    ██║ ╚═╝ ██║██║██║ ╚████║██████╔╝██║ ╚═╝ ██║██║  ██║   ██║   ███████╗
    ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═╝   ╚═╝   ╚══════╝
================================================================================
"""
    logger.info(banner)
    
    # Get the primary URL to display
    if host == '0.0.0.0':
        primary_url = f"http://localhost:{port}"
        local_ip = get_local_ip()
        network_url = f"http://{local_ip}:{port}"
        logger.info(f"🚀 D3.js_Dify is running on:")
        logger.info(f"   Local: {primary_url}")
        logger.info(f"   Network: {network_url}")
    else:
        primary_url = f"http://{host}:{port}"
        logger.info(f"🚀 D3.js_Dify is running on: {primary_url}")
    
    # Print clickable link for terminal
    print(f"\n🌐 Open in browser: {primary_url}\n")

def print_setup_instructions():
    logger.info("""
================================================================================
🚀 D3.js_Dify Setup Instructions

If you are seeing this message, you may be missing required dependencies.

🖥️ Option 1: Run Locally (Recommended for Developers)

1. Install Python dependencies:
   pip install -r requirements.txt

2. Install Node.js (18.19+ or 20+): https://nodejs.org/

3. Install D3.js dependencies:
   cd d3.js
   npm install
   cd ..

4. Install Playwright Chrome browser:
   python -m playwright install chromium

5. Start the Flask app:
   python app.py

6. Open your browser and visit: http://localhost:9527

🐳 Option 2: Run with Docker (No Node.js or Python setup needed)

1. Install Docker: https://www.docker.com/products/docker-desktop
2. Build the Docker image:
   docker build -t d3js-dify .
3. Run the Docker container:
   docker run -p 9527:9527 d3js-dify
4. Open your browser and visit: http://localhost:9527

📋 Manual Dependency Check

If you want to check dependencies manually:
- Python packages: pip list
- Node.js version: node --version
- npm version: npm --version
- D3.js dependencies: cd d3.js && npm list
- Playwright browsers: python -m playwright --version
================================================================================
""")

# Dependency checks before starting the app


if __name__ == '__main__':
    # Record application start time
    app.start_time = time.time()
    
    logger.info("🚀 Starting D3.js_Dify application")
    
    # Run comprehensive dependency checks using individual functions
    try:
        python_ok = dep_checker.check_python_packages(verbose=False)
        nodejs_ok = dep_checker.check_nodejs_installation(verbose=False)
        d3js_ok = dep_checker.check_d3js_dependencies(verbose=False)
        playwright_ok = dep_checker.check_playwright_browsers(verbose=False)
        
        dependencies_ok = python_ok and nodejs_ok and d3js_ok and playwright_ok
        
        if dependencies_ok:
            logger.info("✅ Application dependencies are installed")
        else:
            logger.warning("⚠️  Some dependencies are missing, but the application will continue running.")
            logger.info("💡 You can install missing dependencies later using:")
            logger.info("   python dependency_checker/check_dependencies.py")
    except Exception as e:
        logger.warning(f"⚠️  Dependency check failed: {e}")
        logger.info("💡 The application will continue running, but some features may not work.")
        logger.info("💡 You can check dependencies manually using:")
        logger.info("   python dependency_checker/check_dependencies.py")
    
    # Validate configuration
    if not config.validate_qwen_config():
        logger.error("❌ Invalid Qwen configuration. Please check your environment variables.")
        logger.error("❌ Application cannot start without valid Qwen configuration.")
        sys.exit(1)
    
    if not config.validate_numeric_config():
        logger.error("❌ Invalid numeric configuration. Please check your environment variables.")
        logger.error("❌ Application cannot start with invalid configuration.")
        sys.exit(1)
    
    print_banner(config.HOST, config.PORT)
    
    # Open browser automatically
    open_browser_demo(config.HOST, config.PORT)
    
    # Suppress Flask development server messages
    import logging
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    app.run(debug=config.DEBUG, host=config.HOST, port=config.PORT) 