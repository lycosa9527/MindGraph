"""
MindGraph - AI-Powered Graph Generation Application (FastAPI)
==============================================================

Modern async web application for AI-powered diagram generation.

Version: See VERSION file (centralized version management)
Author: lycosa9527
Made by: MindSpring Team
License: AGPLv3

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
import io
import logging
import time
import signal
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from services.temp_image_cleaner import start_cleanup_scheduler

# Load environment variables
load_dotenv()

# Create logs directory
os.makedirs("logs", exist_ok=True)

# Import config early (needed for logging setup)
from config.settings import config

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

# ============================================================================
# PORT AVAILABILITY CHECK & CLEANUP
# ============================================================================

def _check_port_available(host: str, port: int):
    """
    Check if a port is available for binding.
    
    Args:
        host: Host address to check
        port: Port number to check
        
    Returns:
        tuple: (is_available: bool, pid_using_port: Optional[int])
    """
    import socket
    
    # Try to bind to the port
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.close()
        return (True, None)
    except OSError as e:
        # Port is in use - try to find the process
        if e.errno in (10048, 98):  # Windows: 10048, Linux: 98 (EADDRINUSE)
            pid = _find_process_on_port(port)
            return (False, pid)
        # Other error - re-raise
        raise

def _find_process_on_port(port: int):
    """
    Find the PID of the process using the specified port.
    Cross-platform implementation.
    
    Args:
        port: Port number to check
        
    Returns:
        Optional[int]: PID of process using the port, or None if not found
    """
    import subprocess
    
    try:
        if sys.platform == 'win32':
            # Windows: use netstat
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        return int(parts[-1])
        else:
            # Linux/Mac: use lsof
            result = subprocess.run(
                ['lsof', '-ti', f':{port}'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.stdout.strip():
                return int(result.stdout.strip())
    except Exception as e:
        logger.warning(f"Could not detect process on port {port}: {e}")
    
    return None

def _cleanup_stale_process(pid: int, port: int) -> bool:
    """
    Attempt to gracefully terminate a stale server process.
    
    Args:
        pid: Process ID to terminate
        port: Port number (for logging)
        
    Returns:
        bool: True if cleanup successful, False otherwise
    """
    import subprocess
    
    logger.warning(f"Found process {pid} using port {port}")
    logger.info(f"Attempting to terminate stale server process...")
    
    try:
        if sys.platform == 'win32':
            # Windows: taskkill
            # First try graceful termination
            subprocess.run(
                ['taskkill', '/PID', str(pid)],
                capture_output=True,
                timeout=3
            )
            time.sleep(1)
            
            # Check if still running
            check_result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {pid}'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if str(pid) in check_result.stdout:
                # Force kill if graceful failed
                logger.info("Process still running, forcing termination...")
                subprocess.run(
                    ['taskkill', '/F', '/PID', str(pid)],
                    capture_output=True,
                    timeout=2
                )
        else:
            # Linux/Mac: kill
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # Process already terminated
        
        # Wait for port to be released
        time.sleep(1)
        is_available, _ = _check_port_available('0.0.0.0', port)
        
        if is_available:
            logger.info(f"✅ Successfully cleaned up stale process (PID: {pid})")
            return True
        else:
            logger.error(f"❌ Port {port} still in use after cleanup attempt")
            return False
            
    except Exception as e:
        logger.error(f"Failed to cleanup process {pid}: {e}")
        return False

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
            source = 'MAIN'
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
        elif source.startswith('clients'):
            source = 'CLIE'
        elif source.startswith('services'):
            source = 'SERV'
        elif source.startswith('agents'):
            source = 'AGNT'
        else:
            source = source[:4].upper()
        
        source = source.ljust(4)
        
        return f"[{timestamp}] {colored_level} | {source} | {record.getMessage()}"

# Configure logging
unified_formatter = UnifiedFormatter()

# Use UTF-8 encoding for console output to handle emojis and Chinese characters
console_handler = logging.StreamHandler(
    io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
)
console_handler.setFormatter(unified_formatter)

file_handler = logging.FileHandler(
    os.path.join("logs", "app.log"),
    encoding="utf-8"
)
file_handler.setFormatter(unified_formatter)

# Determine log level (override with DEBUG if VERBOSE_LOGGING is enabled)
if config.VERBOSE_LOGGING:
    log_level = logging.DEBUG
    print(f"[INIT] VERBOSE_LOGGING enabled - setting log level to DEBUG")
else:
    log_level_str = config.LOG_LEVEL
    log_level = getattr(logging, log_level_str, logging.INFO)

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

# Create main logger early
logger = logging.getLogger(__name__)

# Configure dedicated frontend logger with separate file
frontend_file_handler = logging.FileHandler(
    os.path.join("logs", "frontend.log"),
    encoding="utf-8"
)
frontend_file_handler.setFormatter(unified_formatter)

frontend_logger = logging.getLogger('frontend')
frontend_logger.setLevel(logging.DEBUG)  # Always accept all frontend logs
frontend_logger.handlers = []  # Remove default handlers
frontend_logger.addHandler(console_handler)  # Also show in console
frontend_logger.addHandler(frontend_file_handler)  # Dedicated frontend log file
frontend_logger.propagate = False  # Don't propagate to root logger

if os.getenv('UVICORN_WORKER_ID') is None:
    logger.debug("Frontend logger configured with dedicated log file: logs/frontend.log")

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

# Add filter to main logger
logger.addFilter(CancelledErrorFilter())

# Only log from main process, not each worker
if os.getenv('UVICORN_WORKER_ID') is None:
    logger.debug(f"Logging initialized: {log_level_str}")

# ============================================================================
# FASTAPI APPLICATION IMPORTS
# ============================================================================

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

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
    
    # Only log startup banner from first worker to avoid repetition
    worker_id = os.getenv('UVICORN_WORKER_ID', '0')
    if worker_id == '0' or not worker_id:
        logger.info("=" * 80)
        logger.info("FastAPI Application Starting")
        logger.info("=" * 80)
    
    # Initialize JavaScript cache (log only from first worker)
    try:
        from static.js.lazy_cache_manager import lazy_js_cache
        if not lazy_js_cache.is_initialized():
            logger.error("JavaScript cache failed to initialize")
        elif worker_id == '0' or not worker_id:
            logger.info("JavaScript cache initialized successfully")
    except Exception as e:
        if worker_id == '0' or not worker_id:
            logger.warning(f"Failed to initialize JavaScript cache: {e}")
    
    # Initialize Database
    try:
        from config.database import init_db
        from utils.auth import display_demo_info
        init_db()
        if worker_id == '0' or not worker_id:
            logger.info("Database initialized successfully")
            # Display demo info if in demo mode
            display_demo_info()
    except Exception as e:
        if worker_id == '0' or not worker_id:
            logger.error(f"Failed to initialize database: {e}")
    
    # Initialize LLM Service
    try:
        from services.llm_service import llm_service
        llm_service.initialize()
        if worker_id == '0' or not worker_id:
            logger.info("LLM Service initialized")
    except Exception as e:
        if worker_id == '0' or not worker_id:
            logger.warning(f"Failed to initialize LLM Service: {e}")
    
    # Start temp image cleanup task
    cleanup_task = None
    try:
        cleanup_task = asyncio.create_task(start_cleanup_scheduler(interval_hours=1))
        if worker_id == '0' or not worker_id:
            logger.info("Temp image cleanup scheduler started")
    except Exception as e:
        if worker_id == '0' or not worker_id:
            logger.warning(f"Failed to start cleanup scheduler: {e}")
    
    # Yield control to application
    try:
        yield
    finally:
        # Shutdown - clean up resources gracefully
        app.state.is_shutting_down = True
        
        # Give ongoing requests a brief moment to complete
        await asyncio.sleep(0.1)
        
        # Stop cleanup task
        if cleanup_task:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
            if worker_id == '0' or not worker_id:
                logger.info("Temp image cleanup scheduler stopped")
        
        # Cleanup LLM Service
        try:
            from services.llm_service import llm_service
            llm_service.cleanup()
            if worker_id == '0' or not worker_id:
                logger.info("LLM Service cleaned up")
        except Exception as e:
            if worker_id == '0' or not worker_id:
                logger.warning(f"Failed to cleanup LLM Service: {e}")
        
        # Cleanup Database
        try:
            from config.database import close_db
            close_db()
            if worker_id == '0' or not worker_id:
                logger.info("Database connections closed")
        except Exception as e:
            if worker_id == '0' or not worker_id:
                logger.warning(f"Failed to close database: {e}")
        
        # Don't try to cancel tasks - let uvicorn handle the shutdown
        # This prevents CancelledError exceptions during multiprocess shutdown

# ============================================================================
# FASTAPI APPLICATION INITIALIZATION
# ============================================================================

app = FastAPI(
    title="MindGraph API",
    description="AI-Powered Graph Generation with FastAPI + Uvicorn",
    version=config.VERSION,
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

# Jinja2 templates with auto-reload enabled
templates = Jinja2Templates(directory="templates")
templates.env.auto_reload = True  # Enable template auto-reload for development

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
    return {"status": "ok", "version": config.VERSION}

@app.get("/status")
async def get_status():
    """Application status endpoint with metrics"""
    import psutil
    
    memory = psutil.virtual_memory()
    uptime = time.time() - app.state.start_time if hasattr(app.state, 'start_time') else 0
    
    return {
        "status": "running",
        "framework": "FastAPI",
        "version": config.VERSION,
        "uptime_seconds": round(uptime, 1),
        "memory_percent": round(memory.percent, 1),
        "timestamp": time.time()
    }

# ============================================================================
# ROUTER REGISTRATION
# ============================================================================

from routers import pages, cache, api, thinking, auth, admin_env, admin_logs, voice
# from routers import learning  # DISABLED - Will be redesigned later

# Register routers
app.include_router(pages.router)
app.include_router(cache.router)
app.include_router(api.router)
# app.include_router(learning.router)  # DISABLED - Learning mode will be redesigned
app.include_router(thinking.router)  # ThinkGuide mode (Socratic guided thinking)
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])  # Authentication system
app.include_router(admin_env.router)  # Admin environment settings management
app.include_router(admin_logs.router)  # Admin log streaming
app.include_router(voice.router)  # VoiceAgent (real-time voice conversation)

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
    
    # Pre-flight port availability check
    logger.info("Checking port availability...")
    is_available, pid_using_port = _check_port_available(config.HOST, config.PORT)
    
    if not is_available:
        logger.warning(f"⚠️  Port {config.PORT} is already in use")
        
        if pid_using_port:
            logger.warning(f"Process {pid_using_port} is using the port")
            
            # Attempt automatic cleanup
            if _cleanup_stale_process(pid_using_port, config.PORT):
                logger.info("✅ Port cleanup successful, proceeding with startup...")
            else:
                logger.error("=" * 80)
                logger.error(f"❌ Cannot start server - port {config.PORT} is still in use")
                logger.error(f"💡 Manual cleanup required:")
                if sys.platform == 'win32':
                    logger.error(f"   Windows: taskkill /F /PID {pid_using_port}")
                else:
                    logger.error(f"   Linux/Mac: kill -9 {pid_using_port}")
                logger.error("=" * 80)
                sys.exit(1)
        else:
            logger.error("=" * 80)
            logger.error(f"❌ Cannot start server - port {config.PORT} is in use")
            logger.error(f"💡 Could not detect the process using the port")
            logger.error(f"   Please check manually and free the port")
            logger.error("=" * 80)
            sys.exit(1)
    else:
        logger.info(f"✅ Port {config.PORT} is available")
    
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

