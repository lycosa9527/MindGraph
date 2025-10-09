"""
MindGraph - AI-Powered Graph Generation Application (FastAPI)
==============================================================

Modern async web application for AI-powered diagram generation.

Version: 4.0.0 (FastAPI)
Author: lycosa9527
Made by: MindSpring Team
License: MIT

Features:
- Full async/await support for 4,000+ concurrent SSE connections
- FastAPI with Pydantic models for type safety
- Uvicorn ASGI server (Windows + Ubuntu compatible)
- Auto-generated OpenAPI documentation at /docs
- Comprehensive logging, middleware, and business logic

Status: Production Ready
"""

import os
import sys
import logging
import time
import signal
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create logs directory
os.makedirs("logs", exist_ok=True)

# ============================================================================
# GRACEFUL SHUTDOWN SIGNAL HANDLING
# ============================================================================

# Global flag to track shutdown state
_shutdown_event = None

def _get_shutdown_event():
    """Get or create shutdown event for current event loop"""
    global _shutdown_event
    try:
        loop = asyncio.get_event_loop()
        if _shutdown_event is None:
            _shutdown_event = asyncio.Event()
        return _shutdown_event
    except RuntimeError:
        return None

def _handle_shutdown_signal(signum, frame):
    """Handle shutdown signals gracefully (SIGINT, SIGTERM)"""
    event = _get_shutdown_event()
    if event and not event.is_set():
        event.set()

class ShutdownErrorFilter:
    """Filter stderr to suppress expected shutdown errors"""
    
    def __init__(self, original_stderr):
        self.original_stderr = original_stderr
        self.buffer = ""
        self.in_traceback = False
        self.suppress_current = False
        
    def write(self, text):
        """Filter text and only write non-shutdown errors"""
        self.buffer += text
        
        # Check for start of traceback
        if 'Process SpawnProcess' in text or 'Traceback (most recent call last)' in text:
            self.in_traceback = True
            self.suppress_current = False
            
        # Check if this traceback is a CancelledError
        if self.in_traceback and 'asyncio.exceptions.CancelledError' in self.buffer:
            self.suppress_current = True
        
        # If we hit a blank line or new process line, decide whether to flush
        if text.strip() == '' or text.startswith('Process '):
            if self.in_traceback and not self.suppress_current:
                # This was a real error, write it
                self.original_stderr.write(self.buffer)
            # Reset state
            if text.strip() == '':
                self.buffer = ""
                self.in_traceback = False
                self.suppress_current = False
        elif not self.in_traceback:
            # Not in a traceback, write immediately
            self.original_stderr.write(text)
            self.buffer = ""
    
    def flush(self):
        """Flush the original stderr"""
        if not self.suppress_current and self.buffer and not self.in_traceback:
            self.original_stderr.write(self.buffer)
        self.original_stderr.flush()
        self.buffer = ""
    
    def __getattr__(self, name):
        """Delegate all other attributes to original stderr"""
        return getattr(self.original_stderr, name)

# ============================================================================
# EARLY LOGGING SETUP
# ============================================================================

log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_str, logging.INFO)

class UnifiedFormatter(logging.Formatter):
    """Unified logging formatter with ANSI color support."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARN': '\033[33m',     # Yellow
        'ERROR': '\033[31m',    # Red
        'CRIT': '\033[35m',     # Magenta
        'RESET': '\033[0m',     # Reset
        'BOLD': '\033[1m',      # Bold
    }
    
    def format(self, record):
        timestamp = self.formatTime(record, '%H:%M:%S')
        
        level_map = {
            'DEBUG': 'DEBUG',
            'INFO': 'INFO',
            'WARNING': 'WARN',
            'ERROR': 'ERROR',
            'CRITICAL': 'CRIT'
        }
        level_name = level_map.get(record.levelname, record.levelname)
        
        color = self.COLORS.get(level_name, '')
        reset = self.COLORS['RESET']
        
        if level_name == 'CRIT':
            colored_level = f"{self.COLORS['BOLD']}{color}{level_name.ljust(5)}{reset}"
        else:
            colored_level = f"{color}{level_name.ljust(5)}{reset}"
        
        # Source abbreviation
        source = record.name
        if source == '__main__':
            source = 'APP'
        elif source == 'frontend':
            source = 'FRNT'
        elif source.startswith('routers'):
            source = 'API'
        elif source == 'settings':
            source = 'CONF'
        elif source.startswith('uvicorn'):
            source = 'SRVR'
        elif source == 'asyncio':
            source = 'ASYN'
        else:
            source = source[:4].upper()
        
        source = source.ljust(4)
        
        return f"[{timestamp}] {colored_level} | {source} | {record.getMessage()}"

# Configure logging
unified_formatter = UnifiedFormatter()

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(unified_formatter)

file_handler = logging.FileHandler(
    os.path.join("logs", "app.log"),
    encoding="utf-8"
)
file_handler.setFormatter(unified_formatter)

logging.basicConfig(
    level=log_level,
    handlers=[console_handler, file_handler],
    force=True
)

# Configure Uvicorn's loggers to use our custom formatter
for uvicorn_logger_name in ['uvicorn', 'uvicorn.error', 'uvicorn.access']:
    uvicorn_logger = logging.getLogger(uvicorn_logger_name)
    uvicorn_logger.handlers = []  # Remove default handlers
    uvicorn_logger.addHandler(console_handler)
    uvicorn_logger.addHandler(file_handler)
    uvicorn_logger.propagate = False

# Suppress asyncio CancelledError during shutdown
class CancelledErrorFilter(logging.Filter):
    """Filter out CancelledError exceptions during graceful shutdown"""
    def filter(self, record):
        if record.exc_info:
            exc_type = record.exc_info[0]
            if exc_type and issubclass(exc_type, asyncio.CancelledError):
                return False
        # Also filter out the multiprocess shutdown tracebacks
        if 'asyncio.exceptions.CancelledError' in record.getMessage():
            return False
        if 'Process SpawnProcess' in record.getMessage() and 'Traceback' in record.getMessage():
            return False
        return True

asyncio_logger = logging.getLogger('asyncio')
asyncio_logger.addFilter(CancelledErrorFilter())

logger = logging.getLogger(__name__)
logger.addFilter(CancelledErrorFilter())
logger.info(f"Logging initialized: {log_level_str}")

# ============================================================================
# FASTAPI APPLICATION IMPORTS
# ============================================================================

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from config.settings import config

# ============================================================================
# LIFESPAN CONTEXT (Startup/Shutdown Events)
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    Handles application initialization and cleanup.
    """
    # Startup
    app.state.start_time = time.time()
    app.state.is_shutting_down = False
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _handle_shutdown_signal)
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    
    logger.info("=" * 80)
    logger.info("FastAPI Application Starting")
    logger.info("=" * 80)
    
    # Initialize JavaScript cache
    try:
        from static.js.lazy_cache_manager import lazy_js_cache
        if not lazy_js_cache.is_initialized():
            logger.error("JavaScript cache failed to initialize")
        else:
            logger.info("JavaScript cache initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize JavaScript cache: {e}")
    
    # Yield control to application
    try:
        yield
    finally:
        # Shutdown - clean up resources gracefully
        app.state.is_shutting_down = True
        
        # Give ongoing requests a brief moment to complete
        await asyncio.sleep(0.1)
        
        # Don't try to cancel tasks - let uvicorn handle the shutdown
        # This prevents CancelledError exceptions during multiprocess shutdown

# ============================================================================
# FASTAPI APPLICATION INITIALIZATION
# ============================================================================

app = FastAPI(
    title="MindGraph API",
    description="AI-Powered Graph Generation with FastAPI + Uvicorn",
    version="4.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# ============================================================================
# MIDDLEWARE CONFIGURATION
# ============================================================================

# CORS Middleware
if config.DEBUG:
    # Development: Allow multiple origins
    server_url = config.SERVER_URL
    allowed_origins = [
        server_url,
        'http://localhost:3000',
        'http://127.0.0.1:9527'
    ]
else:
    # Production: Restrict to specific origins
    server_url = config.SERVER_URL
    allowed_origins = [server_url]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip Compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Custom Request/Response Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Log all HTTP requests and responses with timing information.
    Handles request/response lifecycle events.
    """
    start_time = time.time()
    
    # Block access to deprecated files
    if request.url.path == '/static/js/d3-renderers.js':
        logger.warning(f"BLOCKED: Attempted access to old d3-renderers.js from {request.client.host}")
        return JSONResponse(
            status_code=403,
            content={"error": "Access Denied: This file is deprecated and should not be accessed"}
        )
    
    logger.debug(f"Request: {request.method} {request.url.path} from {request.client.host}")
    
    # Process request
    response = await call_next(request)
    
    # Log response
    response_time = time.time() - start_time
    logger.debug(f"Response: {response.status_code} in {response_time:.3f}s")
    
    # Monitor slow requests
    if 'generate_png' in request.url.path and response_time > 20:
        logger.warning(f"Slow PNG generation: {request.method} {request.url.path} took {response_time:.3f}s")
    elif response_time > 5:
        logger.warning(f"Slow request: {request.method} {request.url.path} took {response_time:.3f}s")
    
    return response

# ============================================================================
# STATIC FILES AND TEMPLATES
# ============================================================================

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory="templates")

# ============================================================================
# GLOBAL EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    logger.warning(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions"""
    logger.error(f"Unhandled exception: {type(exc).__name__}: {exc}", exc_info=True)
    
    error_response = {"error": "An unexpected error occurred. Please try again later."}
    
    # Add debug info in development mode
    if config.DEBUG:
        error_response["debug"] = str(exc)
    
    return JSONResponse(
        status_code=500,
        content=error_response
    )

# ============================================================================
# BASIC HEALTH CHECK ROUTES
# ============================================================================

@app.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {"status": "ok", "version": "4.0.0-fastapi"}

@app.get("/status")
async def get_status():
    """Application status endpoint with metrics"""
    import psutil
    
    memory = psutil.virtual_memory()
    uptime = time.time() - app.state.start_time if hasattr(app.state, 'start_time') else 0
    
    return {
        "status": "running",
        "framework": "FastAPI",
        "version": "4.0.0",
        "uptime_seconds": round(uptime, 1),
        "memory_percent": round(memory.percent, 1),
        "timestamp": time.time()
    }

# ============================================================================
# ROUTER REGISTRATION
# ============================================================================

from routers import pages, cache, api, learning

# Register routers
app.include_router(pages.router)
app.include_router(cache.router)
app.include_router(api.router)
app.include_router(learning.router)  # Learning mode (FastAPI migration complete)

# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # Print configuration summary
    config.print_config_summary()
    
    logger.info("=" * 80)
    logger.info("Starting FastAPI application with Uvicorn")
    logger.info(f"Server: http://{config.HOST}:{config.PORT}")
    logger.info(f"API Docs: http://{config.HOST}:{config.PORT}/docs")
    if config.DEBUG:
        logger.warning("⚠️  Reload mode enabled - may cause slow shutdown (use Ctrl+C twice if needed)")
    logger.info("=" * 80)
    
    # Install stderr filter to suppress multiprocessing shutdown tracebacks
    original_stderr = sys.stderr
    sys.stderr = ShutdownErrorFilter(original_stderr)
    
    # Install custom exception hook to suppress shutdown errors
    original_excepthook = sys.excepthook
    
    def custom_excepthook(exc_type, exc_value, exc_traceback):
        """Custom exception hook to suppress expected shutdown errors"""
        # Suppress CancelledError during shutdown
        if exc_type == asyncio.CancelledError:
            return
        # Suppress BrokenPipeError and ConnectionResetError during shutdown
        if exc_type in (BrokenPipeError, ConnectionResetError):
            return
        # Call original handler for other exceptions
        original_excepthook(exc_type, exc_value, exc_traceback)
    
    sys.excepthook = custom_excepthook
    
    try:
        # Run Uvicorn server with optimized shutdown settings
        uvicorn.run(
            "main:app",
            host=config.HOST,
            port=config.PORT,
            reload=config.DEBUG,  # Auto-reload in debug mode
            log_level="info",
            log_config=None,  # Use our custom logging configuration
            timeout_graceful_shutdown=5,  # Fast shutdown for cleaner exit
            limit_concurrency=1000,  # Prevent too many hanging connections
            timeout_keep_alive=5  # Close idle connections faster
        )
    except KeyboardInterrupt:
        # Graceful shutdown on Ctrl+C
        logger.info("=" * 80)
        logger.info("Shutting down gracefully...")
        logger.info("=" * 80)
    finally:
        # Restore original stderr and exception hook
        sys.stderr = original_stderr
        sys.excepthook = original_excepthook

