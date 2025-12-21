"""
MindGraph - AI-Powered Graph Generation Application (FastAPI)
==============================================================

Modern async web application for AI-powered diagram generation.

Version: See VERSION file (centralized version management)
Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License

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
from logging.handlers import TimedRotatingFileHandler, BaseRotatingHandler
import time
import signal
import asyncio
import re
from urllib.parse import urlparse
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from dotenv import load_dotenv
from services.temp_image_cleaner import start_cleanup_scheduler
from services.captcha_storage import start_captcha_cleanup_scheduler
from services.backup_scheduler import start_backup_scheduler
from utils.env_utils import ensure_utf8_env_file

# Fix for Windows: Set event loop policy to support subprocesses (required for Playwright)
# MUST be set before any event loop is created (before Uvicorn starts)
if sys.platform == 'win32':
    try:
        current_policy = asyncio.get_event_loop_policy()
        if not isinstance(current_policy, asyncio.WindowsProactorEventLoopPolicy):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            logging.info("Windows: Set event loop policy to WindowsProactorEventLoopPolicy for Playwright support")
    except Exception as e:
        # If we can't check/set, try to set it anyway
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            logging.info("Windows: Set event loop policy to WindowsProactorEventLoopPolicy (unconditional)")
        except Exception as e2:
            logging.warning(f"Windows: Could not set event loop policy: {e2}")

# Ensure .env file is UTF-8 encoded before loading
ensure_utf8_env_file()
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


class TimestampedRotatingFileHandler(BaseRotatingHandler):
    """
    Custom file handler that creates a new timestamped log file every 72 hours.
    Each file is named with the start timestamp of its 72-hour period.
    Example: app.2025-01-15_00-00-00.log
    """
    
    def __init__(self, base_filename, interval_hours=72, backup_count=10, encoding='utf-8'):
        """
        Initialize the handler.
        
        Args:
            base_filename: Base log file path (e.g., 'logs/app.log')
            interval_hours: Hours between rotations (default: 72)
            backup_count: Number of backup files to keep (default: 10)
            encoding: File encoding (default: 'utf-8')
        """
        self.base_filename = base_filename
        self.interval_hours = interval_hours
        self.backup_count = backup_count
        self.interval_seconds = interval_hours * 3600
        
        # Calculate the start of the current 72-hour period
        self.current_period_start = self._get_period_start()
        
        # Generate the filename for the current period
        current_filename = self._get_current_filename()
        
        # Ensure directory exists
        log_dir = os.path.dirname(current_filename)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        # Initialize base handler with current filename
        BaseRotatingHandler.__init__(self, current_filename, 'a', encoding=encoding, delay=False)
        
        # Schedule next rotation check
        self.next_rotation_time = self.current_period_start + timedelta(hours=interval_hours)
    
    def _get_period_start(self):
        """Calculate the start timestamp of the current 72-hour period."""
        now = datetime.now()
        # Calculate how many 72-hour periods have passed since epoch
        seconds_since_epoch = (now - datetime(1970, 1, 1)).total_seconds()
        periods_passed = int(seconds_since_epoch / self.interval_seconds)
        period_start_seconds = periods_passed * self.interval_seconds
        return datetime.fromtimestamp(period_start_seconds)
    
    def _get_current_filename(self):
        """Generate filename for the current period."""
        timestamp_str = self.current_period_start.strftime('%Y-%m-%d_%H-%M-%S')
        base_dir = os.path.dirname(self.base_filename) or '.'
        base_name = os.path.basename(self.base_filename)
        # Remove .log extension if present, add timestamp, then add .log back
        if base_name.endswith('.log'):
            base_name = base_name[:-4]
        return os.path.join(base_dir, f"{base_name}.{timestamp_str}.log")
    
    def shouldRollover(self, record):
        """Check if we should rollover to a new file."""
        now = datetime.now()
        return now >= self.next_rotation_time
    
    def doRollover(self):
        """Perform rollover to a new timestamped file."""
        if self.stream:
            self.stream.close()
            self.stream = None
        
        # Clean up old files
        self._cleanup_old_files()
        
        # Calculate new period start
        self.current_period_start = self._get_period_start()
        self.next_rotation_time = self.current_period_start + timedelta(hours=self.interval_hours)
        
        # Open new file
        new_filename = self._get_current_filename()
        self.baseFilename = new_filename
        self.stream = self._open()
    
    def _cleanup_old_files(self):
        """Remove old log files beyond backup_count."""
        base_dir = os.path.dirname(self.base_filename) or '.'
        base_name = os.path.basename(self.base_filename)
        if base_name.endswith('.log'):
            base_name = base_name[:-4]
        
        # Find all matching log files
        log_files = []
        try:
            for filename in os.listdir(base_dir):
                if filename.startswith(base_name + '.') and filename.endswith('.log'):
                    try:
                        filepath = os.path.join(base_dir, filename)
                        mtime = os.path.getmtime(filepath)
                        log_files.append((mtime, filepath))
                    except OSError:
                        continue
        except OSError:
            # Directory doesn't exist or can't be read, skip cleanup
            pass
        
        # Sort by modification time (oldest first)
        log_files.sort()
        
        # Remove files beyond backup_count
        if len(log_files) > self.backup_count:
            for _, filepath in log_files[:-self.backup_count]:
                try:
                    os.remove(filepath)
                except OSError:
                    pass


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
        elif source == 'openai':
            source = 'OPEN'
        else:
            source = source[:4].upper()
        
        source = source.ljust(4)
        
        # Add process ID to identify worker
        import os
        pid = os.getpid()
        
        return f"[{timestamp}] {colored_level} | {source} | [{pid}] {record.getMessage()}"

# Configure logging
unified_formatter = UnifiedFormatter()

# Use UTF-8 encoding for console output to handle emojis and Chinese characters
console_handler = logging.StreamHandler(
    io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
)
console_handler.setFormatter(unified_formatter)

# Use custom TimestampedRotatingFileHandler to create timestamped log files every 72 hours
# Each file is named with the start timestamp: app.YYYY-MM-DD_HH-MM-SS.log
file_handler = TimestampedRotatingFileHandler(
    os.path.join("logs", "app.log"),
    interval_hours=72,  # Every 72 hours (3 days)
    backup_count=10,  # Keep 10 backup files (30 days of logs)
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

# Filter to downgrade "Invalid HTTP request" warnings from uvicorn to DEBUG level
# These are usually harmless client errors (bots, scanners, malformed requests)
class UvicornInvalidRequestFilter(logging.Filter):
    """Filter to downgrade uvicorn 'Invalid HTTP request' warnings to DEBUG level."""
    def filter(self, record):
        # If this is a WARNING about invalid HTTP request, downgrade to DEBUG
        if record.levelno == logging.WARNING:
            message = record.getMessage()
            if 'Invalid HTTP request' in message or 'invalid request' in message.lower():
                record.levelno = logging.DEBUG
                record.levelname = 'DEBUG'
        return True

# Configure Uvicorn's loggers to use our custom formatter
# Note: uvicorn.access is excluded - access_log=False in run_server.py disables HTTP request logging
for uvicorn_logger_name in ['uvicorn', 'uvicorn.error']:
    uvicorn_logger = logging.getLogger(uvicorn_logger_name)
    uvicorn_logger.handlers = []  # Remove default handlers
    uvicorn_logger.addHandler(console_handler)
    uvicorn_logger.addHandler(file_handler)
    uvicorn_logger.addFilter(UvicornInvalidRequestFilter())  # Downgrade invalid request warnings
    uvicorn_logger.propagate = False

# Create main logger early
logger = logging.getLogger(__name__)

# Configure frontend logger to use the same app.log file
# Frontend logs are tagged with [FRNT] by UnifiedFormatter, so they can be filtered if needed
frontend_logger = logging.getLogger('frontend')
frontend_logger.setLevel(logging.DEBUG)  # Always accept all frontend logs
frontend_logger.handlers = []  # Remove default handlers
frontend_logger.addHandler(console_handler)  # Also show in console
frontend_logger.addHandler(file_handler)  # Write to same app.log file as backend logs
frontend_logger.propagate = False  # Don't propagate to root logger to avoid double logging

if os.getenv('UVICORN_WORKER_ID') is None:
    logger.debug("Frontend logger configured to write to unified log file: logs/app.log")

# Suppress asyncio CancelledError and Windows Proactor errors during shutdown
# IMPORTANT: Never suppress WARNING or ERROR level logs - only suppress DEBUG/INFO for harmless errors
class CancelledErrorFilter(logging.Filter):
    """Filter out CancelledError and Windows Proactor errors during graceful shutdown.
    
    CRITICAL: This filter NEVER suppresses WARNING or ERROR level logs.
    Only DEBUG and INFO level logs for known harmless errors are filtered.
    """
    def filter(self, record):
        # CRITICAL: NEVER suppress WARNING, ERROR, or CRITICAL level logs
        # Always allow through any log at WARNING level or above
        if record.levelno >= logging.WARNING:
            return True
        
        # Only filter DEBUG and INFO level logs for known harmless errors
        if record.exc_info:
            exc_type = record.exc_info[0]
            if exc_type and issubclass(exc_type, asyncio.CancelledError):
                return False
        message = record.getMessage()
        # Filter out CancelledError messages (only at DEBUG/INFO level)
        if 'asyncio.exceptions.CancelledError' in message:
            return False
        # Filter out Windows Proactor pipe transport errors (harmless cleanup errors, only at DEBUG/INFO)
        if '_ProactorBasePipeTransport._call_connection_lost' in message:
            return False
        if 'Exception in callback _ProactorBasePipeTransport' in message:
            return False
        # Filter out multiprocess shutdown tracebacks (only at DEBUG/INFO level)
        if 'Process SpawnProcess' in message and 'Traceback' in message:
            return False
        return True

asyncio_logger = logging.getLogger('asyncio')
asyncio_logger.addFilter(CancelledErrorFilter())

# Add filter to main logger
logger.addFilter(CancelledErrorFilter())

# Suppress verbose HTTP client logs (httpx/httpcore make many API calls)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

# Suppress verbose COS SDK logs (qcloud_cos produces excessive DEBUG logs during backup)
# The backup_scheduler service logs are tagged with SERV, these external libs should be quiet
logging.getLogger('qcloud_cos').setLevel(logging.WARNING)
logging.getLogger('qcloud_cos.cos_client').setLevel(logging.WARNING)
logging.getLogger('qcloud_cos.cos_auth').setLevel(logging.WARNING)

# Suppress verbose urllib3 connection pool logs (used by COS SDK and other HTTP clients)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)

class OpenAIHTTPLogFilter(logging.Filter):
    """Filter to reformat OpenAI SDK HTTP logs to match project log format.
    
    Reformats verbose HTTP request/response logs from OpenAI SDK into concise format:
    - "HTTP Response: POST https://api.hunyuan.cloud.tencent.com/v1/chat/completions "200 OK" Headers({...})"
      → "Hunyuan API: POST /v1/chat/completions → 200 OK"
    """
    
    # API name mapping: URL substring -> Display name
    API_NAMES = {
        'hunyuan': 'Hunyuan',
        'doubao': 'Doubao',
        'dashscope': 'DashScope',
        'openai': 'OpenAI',
        'anthropic': 'Anthropic',
    }
    
    def _extract_api_name(self, url: str) -> str:
        """Extract API name from URL."""
        url_lower = url.lower()
        for key, name in self.API_NAMES.items():
            if key in url_lower:
                return name
        return 'LLM'
    
    def _extract_endpoint(self, url: str) -> str:
        """Extract endpoint path from URL."""
        try:
            parsed = urlparse(url)
            return parsed.path or '/'
        except (ValueError, AttributeError, TypeError):
            # Fallback: extract path manually
            if '://' in url:
                path_part = url.split('://', 1)[1]
                if '/' in path_part:
                    return '/' + path_part.split('/', 1)[1].split('?')[0]
            return url.split('/')[-1] if '/' in url else url
    
    def _reformat_response(self, message: str) -> str:
        """Reformat HTTP Response message."""
        # Pattern: "HTTP Response: METHOD URL "STATUS_CODE STATUS_TEXT" ..."
        # More flexible regex to handle various formats
        pattern = r'HTTP Response:\s+(\w+)\s+(https?://[^\s"]+)\s+"(\d+)\s+([^"]+)"'
        match = re.match(pattern, message)
        if match:
            method, url, status_code, status_text = match.groups()
            api_name = self._extract_api_name(url)
            endpoint = self._extract_endpoint(url)
            return f"{api_name} API: {method} {endpoint} → {status_code} {status_text}"
        return message  # Return original if pattern doesn't match
    
    def _reformat_request(self, message: str) -> str:
        """Reformat HTTP Request message."""
        # Pattern: "HTTP Request: METHOD URL ..."
        pattern = r'HTTP Request:\s+(\w+)\s+(https?://[^\s]+)'
        match = re.match(pattern, message)
        if match:
            method, url = match.groups()
            api_name = self._extract_api_name(url)
            endpoint = self._extract_endpoint(url)
            return f"{api_name} API: {method} {endpoint}"
        return message  # Return original if pattern doesn't match
    
    def filter(self, record):
        """Reformat HTTP request/response messages from OpenAI SDK."""
        # Only process if message hasn't been reformatted yet
        if hasattr(record, '_openai_reformatted'):
            return True
        
        # Get message string (avoid calling getMessage() if possible)
        if isinstance(record.msg, str):
            message = record.msg
        elif record.args:
            # Only call getMessage() if args exist (format string)
            message = record.getMessage()
        else:
            message = str(record.msg)
        
        # Reformat HTTP Response messages
        if message.startswith('HTTP Response:'):
            reformatted = self._reformat_response(message)
            record.msg = reformatted
            record.args = ()
            record._openai_reformatted = True
        
        # Reformat HTTP Request messages
        elif message.startswith('HTTP Request:'):
            reformatted = self._reformat_request(message)
            record.msg = reformatted
            record.args = ()
            record._openai_reformatted = True
        
        return True

# Enable OpenAI SDK logging for HTTP request/response visibility
# This provides detailed logs for Hunyuan and Doubao API calls
# Respect global LOG_LEVEL setting - only show DEBUG logs if LOG_LEVEL=DEBUG
openai_logger = logging.getLogger('openai')
openai_logger.setLevel(log_level)  # Use global log level instead of hardcoded DEBUG
openai_logger.handlers = []  # Remove default handlers
openai_logger.addHandler(console_handler)
openai_logger.addHandler(file_handler)
openai_logger.addFilter(OpenAIHTTPLogFilter())
openai_logger.propagate = False

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
from fastapi.exceptions import RequestValidationError
from models.responses import DatabaseHealthResponse

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
            logger.info(f"JavaScript cache initialized (version: {config.VERSION})")
    except Exception as e:
        if worker_id == '0' or not worker_id:
            logger.warning(f"Failed to initialize JavaScript cache: {e}")
    
    # Initialize Database with corruption detection and recovery
    try:
        from config.database import init_db
        from utils.auth import display_demo_info
        from services.database_recovery import check_database_on_startup
        
        # Check database integrity on startup (only on worker 0)
        # If corruption is detected, interactive recovery wizard is triggered
        if worker_id == '0' or not worker_id:
            if not check_database_on_startup():
                logger.critical("Database recovery failed or was aborted. Shutting down.")
                raise SystemExit(1)
            logger.info("Database integrity verified")
        
        init_db()
        if worker_id == '0' or not worker_id:
            logger.info("Database initialized successfully")
            # Display demo info if in demo mode
            display_demo_info()
    except SystemExit:
        raise  # Re-raise SystemExit to abort startup
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
    
    # Verify Playwright installation (for PNG generation)
    if worker_id == '0' or not worker_id:
        try:
            from services.browser import log_browser_diagnostics
            await log_browser_diagnostics()
        except NotImplementedError:
            logger.error("=" * 80)
            logger.error("CRITICAL: Playwright browsers are not installed!")
            logger.error("PNG generation endpoints (/api/generate_png, /api/generate_dingtalk) will fail.")
            logger.error("To fix: conda activate python3.13 && playwright install chromium")
            logger.error("=" * 80)
        except Exception as e:
            logger.warning("Could not verify Playwright installation: %s", e)
    
    # Start temp image cleanup task
    cleanup_task = None
    try:
        cleanup_task = asyncio.create_task(start_cleanup_scheduler(interval_hours=1))
        if worker_id == '0' or not worker_id:
            logger.info("Temp image cleanup scheduler started")
    except Exception as e:
        if worker_id == '0' or not worker_id:
            logger.warning(f"Failed to start cleanup scheduler: {e}")
    
    # Start captcha cleanup task (removes expired captchas every 10 minutes)
    captcha_cleanup_task = None
    try:
        captcha_cleanup_task = asyncio.create_task(start_captcha_cleanup_scheduler(interval_minutes=10))
        if worker_id == '0' or not worker_id:
            logger.info("Captcha cleanup scheduler started")
    except Exception as e:
        if worker_id == '0' or not worker_id:
            logger.warning(f"Failed to start captcha cleanup scheduler: {e}")
    
    # Start WAL checkpoint scheduler (checkpoints SQLite WAL every 5 minutes)
    # This is critical for database safety, especially when using kill -9 (SIGKILL)
    # which bypasses graceful shutdown. Periodic checkpointing ensures WAL file
    # doesn't grow too large and reduces corruption risk.
    wal_checkpoint_task = None
    try:
        from config.database import start_wal_checkpoint_scheduler
        wal_checkpoint_task = asyncio.create_task(start_wal_checkpoint_scheduler(interval_minutes=5))
        if worker_id == '0' or not worker_id:
            logger.info("WAL checkpoint scheduler started (every 5 min)")
    except Exception as e:
        if worker_id == '0' or not worker_id:
            logger.warning(f"Failed to start WAL checkpoint scheduler: {e}")
    
    # Start database backup scheduler (daily automatic backups)
    # Backs up SQLite database daily, keeps configurable retention (default: 2 backups)
    # Only run on worker 0 to avoid multiple workers backing up simultaneously
    backup_scheduler_task = None
    if worker_id == '0' or not worker_id:
        try:
            backup_scheduler_task = asyncio.create_task(start_backup_scheduler())
            logger.info("Database backup scheduler started")
        except Exception as e:
            logger.warning(f"Failed to start backup scheduler: {e}")
    
    # Yield control to application
    try:
        yield
    finally:
        # Shutdown - clean up resources gracefully
        app.state.is_shutting_down = True
        
        # Give ongoing requests a brief moment to complete
        await asyncio.sleep(0.1)
        
        # Stop cleanup tasks
        if cleanup_task:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
            if worker_id == '0' or not worker_id:
                logger.info("Temp image cleanup scheduler stopped")
        
        if captcha_cleanup_task:
            captcha_cleanup_task.cancel()
            try:
                await captcha_cleanup_task
            except asyncio.CancelledError:
                pass
            if worker_id == '0' or not worker_id:
                logger.info("Captcha cleanup scheduler stopped")
        
        # Stop WAL checkpoint scheduler
        if wal_checkpoint_task:
            wal_checkpoint_task.cancel()
            try:
                await wal_checkpoint_task
            except asyncio.CancelledError:
                pass
            if worker_id == '0' or not worker_id:
                logger.info("WAL checkpoint scheduler stopped")
        
        # Stop backup scheduler (only runs on worker 0)
        if backup_scheduler_task:
            backup_scheduler_task.cancel()
            try:
                await backup_scheduler_task
            except asyncio.CancelledError:
                pass
            logger.info("Database backup scheduler stopped")
        
        # Cleanup LLM Service
        try:
            from services.llm_service import llm_service
            llm_service.cleanup()
            if worker_id == '0' or not worker_id:
                logger.info("LLM Service cleaned up")
        except Exception as e:
            if worker_id == '0' or not worker_id:
                logger.warning(f"Failed to cleanup LLM Service: {e}")
        
        # Flush update notification dismiss buffer
        try:
            from services.update_notifier import update_notifier
            update_notifier.shutdown()
            if worker_id == '0' or not worker_id:
                logger.info("Update notifier flushed")
        except Exception as e:
            if worker_id == '0' or not worker_id:
                logger.warning(f"Failed to flush update notifier: {e}")
        
        # Flush TokenTracker before closing database
        try:
            from services.token_tracker import get_token_tracker
            token_tracker = get_token_tracker()
            await token_tracker.flush()
            if worker_id == '0' or not worker_id:
                logger.info("TokenTracker flushed")
        except Exception as e:
            if worker_id == '0' or not worker_id:
                logger.warning(f"Failed to flush TokenTracker: {e}")
        
        # Shutdown SMS service (close httpx async client)
        try:
            from services.sms_middleware import shutdown_sms_service
            await shutdown_sms_service()
            if worker_id == '0' or not worker_id:
                logger.info("SMS service shut down")
        except Exception as e:
            if worker_id == '0' or not worker_id:
                logger.warning(f"Failed to shutdown SMS service: {e}")
        
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
    # Disable Swagger UI in production for security (only enable in DEBUG mode)
    docs_url="/docs" if config.DEBUG else None,
    redoc_url="/redoc" if config.DEBUG else None,
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

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Add security headers to all HTTP responses.
    
    Protects against:
    - Clickjacking (X-Frame-Options)
    - MIME sniffing attacks (X-Content-Type-Options)
    - XSS attacks (X-XSS-Protection, Content-Security-Policy)
    - Information leakage (Referrer-Policy)
    
    CSP Policy Notes:
    - 'unsafe-inline' scripts: Required for config bootstrap and admin onclick handlers
    - 'unsafe-eval': Required for D3.js library (data transformations)
    - ws:/wss:: Required for VoiceAgent WebSocket connections
    - data: URIs: Required for canvas-to-image conversions
    - DEBUG mode: Allows Swagger UI CDN (cdn.jsdelivr.net) for /docs endpoint
    
    Reviewed: 2025-10-26 - All directives verified against actual codebase
    """
    response = await call_next(request)
    
    # Prevent clickjacking (stops site being embedded in iframes)
    response.headers["X-Frame-Options"] = "DENY"
    
    # Prevent MIME sniffing (stops browser from guessing content types)
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # XSS Protection (blocks reflected XSS attacks)
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Content Security Policy (controls what resources can load)
    # Tailored specifically for MindGraph's architecture
    # In DEBUG mode, allow Swagger UI CDN for /docs and /redoc endpoints
    if config.DEBUG:
        # DEBUG mode: Allow Swagger UI resources from CDN (including source maps)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: http: https: blob: https://cdn.jsdelivr.net https://fastapi.tiangolo.com; "
            "font-src 'self' data: https://cdn.jsdelivr.net; "
            "connect-src 'self' ws: wss: blob: https://cdn.jsdelivr.net; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
    else:
        # Production: Strict CSP without external CDN access
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: http: https: blob:; "
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss: blob:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
    
    # Referrer Policy (controls info sent in Referer header)
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Permissions Policy (restrict access to browser features)
    # Only allow microphone (for VoiceAgent), disable everything else
    response.headers["Permissions-Policy"] = (
        "microphone=(self), "
        "camera=(), "
        "geolocation=(), "
        "payment=()"
    )
    
    return response

# Static Files Cache Control Middleware
@app.middleware("http")
async def add_cache_control_headers(request: Request, call_next):
    """
    Add cache control headers for static files.
    
    Strategy:
    - Static files with version query string (?v=x.x.x): Cache for 1 year
    - Static files without version: Cache for 1 hour with revalidation
    - HTML pages: No cache (always fetch fresh)
    - API responses: No cache
    
    This ensures users always get the latest code when we update the VERSION file.
    """
    response = await call_next(request)
    
    path = request.url.path
    query = str(request.url.query)
    
    # Static files
    if path.startswith('/static/'):
        # If version query parameter is present, cache aggressively
        if 'v=' in query:
            # Versioned assets can be cached for a long time (1 year)
            # Browser will fetch new version when VERSION changes
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            # Unversioned static files: short cache with revalidation
            response.headers["Cache-Control"] = "public, max-age=3600, must-revalidate"
    # HTML pages: no cache
    elif path.endswith('.html') or path in ['/', '/editor', '/debug', '/auth', '/admin', '/demo']:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    
    return response

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
    
    # For static files, include version query param in log to verify cache busting
    log_path = request.url.path
    if request.url.path.startswith('/static/') and request.url.query:
        log_path = f"{request.url.path}?{request.url.query}"
    
    # Process request
    response = await call_next(request)
    
    # Log combined request/response to save space
    response_time = time.time() - start_time
    logger.debug(f"Request: {request.method} {log_path} from {request.client.host} Response: {response.status_code} in {response_time:.3f}s")
    
    # Monitor slow requests (thresholds based on endpoint type)
    if 'generate_png' in request.url.path and response_time > 20:
        logger.warning(f"Slow PNG generation: {request.method} {request.url.path} took {response_time:.3f}s")
    elif 'generate_graph' in request.url.path and response_time > 5:
        # LLM generation typically takes 2-8s, warn above 5s to catch slow requests early
        logger.warning(f"Slow graph generation: {request.method} {request.url.path} took {response_time:.3f}s")
    elif 'node_palette' in request.url.path and response_time > 10:
        # Node Palette streams from 4 LLMs, 5-8s is normal
        logger.warning(f"Slow node palette: {request.method} {request.url.path} took {response_time:.3f}s")
    elif 'thinking_mode' in request.url.path and response_time > 10:
        # LLM calls take 3-8s normally
        logger.warning(f"Slow thinking mode: {request.method} {request.url.path} took {response_time:.3f}s")
    elif response_time > 5:
        # Other endpoints (static files, auth, etc.) should be fast
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

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle request validation errors (422 Unprocessable Entity).
    
    These occur when request body/parameters don't match the expected schema.
    Common causes: missing required fields, wrong data types, invalid formats.
    """
    path = getattr(request.url, 'path', '') if request and request.url else ''
    
    # Extract validation errors
    errors = exc.errors() if hasattr(exc, 'errors') else []
    error_details = []
    for error in errors:
        loc = error.get('loc', [])
        msg = error.get('msg', '')
        error_details.append(f"{'.'.join(str(x) for x in loc)}: {msg}")
    
    # Log at DEBUG level for common validation issues (expected client errors)
    # Log at WARNING level for unusual validation errors
    error_summary = '; '.join(error_details[:3])  # Show first 3 errors
    if len(error_details) > 3:
        error_summary += f" ... and {len(error_details) - 3} more"
    
    logger.debug(f"Request validation error on {path}: {error_summary}")
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": error_details,
            "message": "Request validation failed. Please check your request parameters."
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Handle HTTP exceptions.
    
    Returns FastAPI-standard format: {"detail": "error message"}
    This matches FastAPI's default HTTPException response format.
    """
    path = getattr(request.url, 'path', '') if request and request.url else ''
    detail = exc.detail or ""
    
    # Suppress warnings for expected security checks:
    # 1. Admin access checks (403 on /api/auth/admin/* endpoints)
    #    The admin button ("后台") calls /api/auth/admin/stats to check admin status
    # 2. Token expiration checks (401 with "Invalid or expired token")
    #    Frontend periodically checks authentication status via /api/auth/me
    # 3. Request validation errors (400) - these are client errors, log at DEBUG
    if exc.status_code == 403 and path.startswith("/api/auth/admin/"):
        logger.debug(f"HTTP {exc.status_code}: {exc.detail} (expected admin check)")
    elif exc.status_code == 401 and "Invalid or expired token" in detail:
        logger.debug(f"HTTP {exc.status_code}: {exc.detail} (expected token expiration check)")
    elif exc.status_code == 400:
        # 400 Bad Request - usually client errors (invalid parameters, malformed requests)
        # Log at DEBUG level to reduce noise (these are expected client errors)
        logger.debug(f"HTTP {exc.status_code} on {path}: {exc.detail}")
    else:
        logger.warning(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}  # Use "detail" to match FastAPI standard
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

@app.get("/health/database", response_model=DatabaseHealthResponse)
async def database_health_check():
    """
    Database health check endpoint.
    
    Returns database integrity status and statistics.
    
    Note: This endpoint performs a fast integrity check. For detailed backup
    information, use the admin panel or recovery tools.
    
    Returns:
        - 200 OK: Database is healthy
        - 503 Service Unavailable: Database is unhealthy or corrupted
        - 500 Internal Server Error: Health check failed
    """
    try:
        from services.database_recovery import DatabaseRecovery
        
        # Fast check - only integrity and basic stats, no backup listing
        # Backup listing can be slow (10-30+ seconds) and is not needed for health checks
        recovery = DatabaseRecovery()
        is_healthy, message = recovery.check_integrity()
        
        # Get basic database stats (fast)
        current_stats = {}
        if recovery.db_path and recovery.db_path.exists():
            try:
                stats = recovery.get_database_stats(recovery.db_path)
                # Only include essential stats for security and performance
                current_stats = {
                    "path": stats.get("path"),
                    "size_mb": stats.get("size_mb"),
                    "modified": stats.get("modified"),
                    "total_rows": stats.get("total_rows"),
                    # Don't expose table names/details for security
                }
            except Exception as e:
                logger.debug(f"Failed to get database stats: {e}")
                # Stats are optional, continue without them
        
        response_data = {
            "status": "healthy" if is_healthy else "unhealthy",
            "database_healthy": is_healthy,
            "database_message": message,
            "database_stats": current_stats,
            "timestamp": int(time.time())
        }
        
        # Return appropriate HTTP status code
        status_code = 200 if is_healthy else 503
        
        return JSONResponse(
            content=response_data,
            status_code=status_code
        )
        
    except ImportError as e:
        logger.error(f"Database recovery module not available: {e}")
        raise HTTPException(
            status_code=503,
            detail="Database health check unavailable"
        )
    except Exception as e:
        logger.error(f"Database health check error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Database health check failed: {str(e)}"
        )

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

from routers import pages, cache, api, node_palette, auth, admin_env, admin_logs, admin_realtime, voice, update_notification, tab_mode

# Register routers
app.include_router(pages.router)
app.include_router(cache.router)
app.include_router(api.router)
app.include_router(node_palette.router)  # Node Palette endpoints
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])  # Authentication system
app.include_router(admin_env.router)  # Admin environment settings management
app.include_router(admin_logs.router)  # Admin log streaming
app.include_router(admin_realtime.router)  # Admin realtime user activity monitoring
app.include_router(voice.router)  # VoiceAgent (real-time voice conversation)
app.include_router(update_notification.router)  # Update notification system
app.include_router(tab_mode.router)  # Tab Mode (autocomplete and expansion)

# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    import asyncio
    import sys
    
    # CRITICAL FIX for Windows: Set event loop policy to support subprocesses
    # Playwright requires subprocess support, which SelectorEventLoop doesn't provide on Windows
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        logger.info("Windows detected: Set event loop policy to WindowsProactorEventLoopPolicy for Playwright support")
    
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

