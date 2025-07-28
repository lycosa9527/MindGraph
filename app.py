"""
MindGraph - AI-Powered Graph Generation Application
===================================================

A Flask-based web application that generates interactive D3.js graphs using AI agents.
Supports both Qwen and DeepSeek LLMs for intelligent graph generation and enhancement.

Version: 2.3.2
Author: MindSpring Team
License: MIT

Features:
- AI-powered graph generation with Qwen and DeepSeek LLMs
- Interactive D3.js visualization
- PNG export functionality
- Comprehensive dependency validation
- Professional startup sequence
- Cross-platform compatibility

Dependencies:
- Python 3.8+
- Flask, LangChain, Playwright, Pillow
- Node.js (for D3.js dependencies)
- Qwen API key (required)
- DeepSeek API key (optional)

Usage:
    python app.py

Environment Variables:
    QWEN_API_KEY: Required for core functionality
    DEEPSEEK_API_KEY: Optional for enhanced features
    See env.example for complete configuration
"""

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
load_dotenv()  # Load environment variables from .env file
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

# ============================================================================
# APPLICATION SETUP AND CONFIGURATION
# ============================================================================

# Create logs directory for application logging
os.makedirs("logs", exist_ok=True)

# Configure logging with clean, professional output
logging.basicConfig(
    level=logging.INFO,  # INFO level for clean console output
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler("logs/app.log", encoding="utf-8")  # File logging
    ]
)
logger = logging.getLogger(__name__)

# Import dependency checker module for comprehensive validation
import dependency_checker.check_dependencies as dep_checker

# ============================================================================
# DEPENDENCY VALIDATION
# ============================================================================

def validate_dependencies():
    """
    Comprehensive dependency and configuration validation.
    
    Validates:
    - Python version (3.8+)
    - Required Python packages
    - Qwen API configuration (required)
    - DeepSeek API configuration (optional)
    - Numeric configuration values
    - Playwright browser installation
    
    Exits with error code 1 if critical dependencies are missing.
    """
    logger.info("🔍 Validating dependencies and configuration...")
    
    # Validate Python version requirement
    if sys.version_info < (3, 8):
        logger.error("❌ Python 3.8 or higher is required")
        sys.exit(1)
    
    # Define required Python packages for core functionality
    required_packages = [
        'flask', 'requests', 'langchain', 'yaml', 'dotenv',
        'nest_asyncio', 'pyee', 'playwright', 'pillow'
    ]
    
    # Package name mapping for correct import checking
    package_mapping = {
        'yaml': 'yaml',      # PyYAML imports as yaml
        'dotenv': 'dotenv',  # python-dotenv imports as dotenv
        'pillow': 'PIL',     # Pillow imports as PIL
    }
    
    # Check each required package
    missing_packages = []
    for package in required_packages:
        try:
            import_name = package_mapping.get(package, package)
            __import__(import_name)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.error(f"❌ Missing required packages: {', '.join(missing_packages)}")
        logger.error("💡 Please install missing packages: pip install -r requirements.txt")
        sys.exit(1)
    
    # Validate Qwen configuration (required for core functionality)
    if not config.validate_qwen_config():
        logger.error("❌ Qwen configuration validation failed")
        logger.error("💡 Please check QWEN_API_KEY and QWEN_API_URL in your environment")
        sys.exit(1)
    
    # Check DeepSeek configuration (optional, for enhanced features)
    if not config.validate_deepseek_config():
        logger.warning("⚠️  DeepSeek configuration not available - features will be disabled")
    
    # Validate numeric configuration values
    if not config.validate_numeric_config():
        logger.error("❌ Invalid numeric configuration")
        logger.error("💡 Please check your environment variables")
        sys.exit(1)
    
    # Ensure Playwright browser is available for PNG generation
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
    except Exception:
        logger.info("📦 Installing Playwright browser...")
        try:
            subprocess.run([sys.executable, '-m', 'playwright', 'install', 'chromium'], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to install Playwright browser: {e}")
            sys.exit(1)
    
    logger.info("✅ All dependencies and configuration validated successfully")

# Run dependency validation before application startup
validate_dependencies()

# ============================================================================
# FLASK APPLICATION INITIALIZATION
# ============================================================================

# Initialize Flask application
app = Flask(__name__)

# ============================================================================
# REQUEST LOGGING AND MONITORING
# ============================================================================

@app.before_request
def log_request():
    """Log incoming HTTP requests with timing information."""
    request.start_time = time.time()
    logger.info(f"Request: {request.method} {request.path} from {request.remote_addr}")

@app.after_request
def log_response(response):
    """
    Log response details and monitor performance.
    
    Features:
    - Response time tracking
    - Slow request detection
    - PNG generation performance monitoring
    """
    if hasattr(request, 'start_time'):
        response_time = time.time() - request.start_time
        logger.info(f"Response: {response.status_code} in {response_time:.3f}s")
        
        # Monitor slow requests with different thresholds
        if 'generate_png' in request.path and response_time > 20:
            logger.warning(f"Slow PNG generation: {request.method} {request.path} took {response_time:.3f}s")
        elif response_time > 5:
            logger.warning(f"Slow request: {request.method} {request.path} took {response_time:.3f}s")
            # Debug logging for PNG-related requests
            if 'png' in request.path.lower() or 'generate' in request.path.lower():
                logger.info(f"DEBUG: PNG-related request path: {request.path}")
    
    return response

# ============================================================================
# CORS AND SECURITY CONFIGURATION
# ============================================================================

# Configure CORS based on environment (development vs production)
if config.DEBUG:
    # Development: Allow multiple origins with restrictions
    CORS(app, origins=['http://localhost:9527', 'http://127.0.0.1:9527', 'http://localhost:3000'])
else:
    # Production: Restrict to specific origins
    CORS(app, origins=[
        'http://localhost:9527',
        'http://127.0.0.1:9527'
        # Add production domains here
    ])

# Configure rate limiting for API protection
limiter = Limiter(get_remote_address, app=app, default_limits=["20 per minute"])

# ============================================================================
# ROUTE REGISTRATION
# ============================================================================

# Register API and web route blueprints
app.register_blueprint(api)
app.register_blueprint(web)

# ============================================================================
# APPLICATION STATUS AND HEALTH CHECKS
# ============================================================================

@app.route('/status')
def get_status():
    """
    Application health check endpoint.
    
    Returns:
        JSON with application status, uptime, and system metrics
    """
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

# ============================================================================
# ERROR HANDLING
# ============================================================================

@app.errorhandler(Exception)
def handle_exception(e):
    """
    Global error handler for unhandled exceptions.
    
    Features:
    - HTTP error pass-through
    - Unhandled exception logging
    - Debug information in development mode
    """
    # Pass through HTTP errors
    if isinstance(e, HTTPException):
        logger.warning(f"HTTP {e.code}: {e.description}")
        return jsonify({'error': e.description}), e.code
    
    # Log unhandled exceptions with full traceback
    logger.error(f"Unhandled exception: {type(e).__name__}: {e}", exc_info=True)
    
    # Return user-friendly error response
    error_response = {'error': 'An unexpected error occurred. Please try again later.'}
    
    # Add debug information in development mode
    if config.DEBUG:
        error_response['debug'] = str(e)
    
    return jsonify(error_response), 500

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_local_ip():
    """
    Get the local IP address for network access.
    
    Returns:
        str: Local IP address or "127.0.0.1" if detection fails
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

def open_browser_debug(host, port):
    """
    Automatically open the debug page in browser with server readiness check.
    
    Features:
    - Waits for server to be ready before opening browser
    - Handles different host configurations
    - Non-blocking browser opening
    """
    try:
        # Determine the correct URL based on host configuration
        if host == '0.0.0.0':
            url = f"http://localhost:{port}/debug"
        else:
            url = f"http://{host}:{port}/debug"
        
        def open_browser():
            """Open browser after confirming server is ready."""
            import requests
            max_attempts = 15
            for attempt in range(max_attempts):
                try:
                    # Check if server is responding
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
        
        # Start browser opening in a separate thread (non-blocking)
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()
        
    except Exception as e:
        logger.warning(f"Could not open browser automatically: {e}")

def print_banner(host, port):
    """
    Display professional startup banner with application information.
    
    Features:
    - ASCII art logo
    - Application URLs (local and network)
    - Clickable browser link
    """
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
    print(banner)
    
    # Display application URLs
    if host == '0.0.0.0':
        primary_url = f"http://localhost:{port}"
        local_ip = get_local_ip()
        network_url = f"http://{local_ip}:{port}"
        print(f"🌐 Application URLs:")
        print(f"   Local: {primary_url}")
        print(f"   Network: {network_url}")
    else:
        primary_url = f"http://{host}:{port}"
        print(f"🌐 Application URL: {primary_url}")
    
    print(f"\n🌐 Open in browser: {primary_url}\n")

def print_setup_instructions():
    """
    Display comprehensive setup instructions for users.
    
    Includes:
    - Local development setup
    - Docker deployment
    - Manual dependency checking
    """
    logger.info("""
================================================================================
🚀 MindGraph Setup Instructions

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
   docker build -t mindgraph .
3. Run the Docker container:
   docker run -p 9527:9527 mindgraph
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

# ============================================================================
# APPLICATION STARTUP
# ============================================================================

if __name__ == '__main__':
    # Record application start time for uptime tracking
    app.start_time = time.time()
    
    logger.info("🚀 Starting MindGraph application...")
    
    # Display configuration summary
    config.print_config_summary()
    
    # Display professional startup banner
    print_banner(config.HOST, config.PORT)
    
    # Automatically open browser (non-blocking)
    open_browser_debug(config.HOST, config.PORT)
    
    # Suppress Flask development server messages for cleaner output
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    logger.info("🌐 Starting Flask development server...")
    app.run(debug=config.DEBUG, host=config.HOST, port=config.PORT) 