"""
Logging configuration for MindGraph application.

Handles:
- Custom file handlers with timestamped rotation
- Unified formatter with ANSI colors
- Logger configuration and filters
- OpenAI SDK HTTP log reformatting
"""

import os
import sys
import logging
import re
from logging.handlers import BaseRotatingHandler
from datetime import datetime, timedelta
from typing import Literal
from urllib.parse import urlparse
from config.settings import config


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
        self.current_period_start = self._get_period_start()  # pylint: disable=protected-access

        # Generate the filename for the current period
        current_filename = self._get_current_filename()  # pylint: disable=protected-access

        # Ensure directory exists
        log_dir = os.path.dirname(current_filename)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        # Initialize base handler with current filename
        BaseRotatingHandler.__init__(self, current_filename, 'a', encoding=encoding, delay=False)

        # Schedule next rotation check
        self.next_rotation_time = self.current_period_start + timedelta(hours=interval_hours)

    def _get_period_start(self) -> datetime:
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

    def should_rollover(self, record):
        """Check if we should rollover to a new file."""
        # Record parameter is required by parent class interface but not used
        # We check time-based rotation instead of record-based
        del record  # Explicitly mark as intentionally unused
        now = datetime.now()
        return now >= self.next_rotation_time

    def do_rollover(self):
        """Perform rollover to a new timestamped file."""
        if self.stream:
            self.stream.close()

        # Clean up old files
        self._cleanup_old_files()  # pylint: disable=protected-access

        # Calculate new period start
        self.current_period_start = self._get_period_start()  # pylint: disable=protected-access
        self.next_rotation_time = self.current_period_start + timedelta(hours=self.interval_hours)

        # Open new file
        new_filename = self._get_current_filename()  # pylint: disable=protected-access
        self.baseFilename = new_filename
        self.stream = self._open()  # pylint: disable=protected-access

    def __getattr__(self, name):
        """Handle camelCase method calls from Python logging framework."""
        if name == 'shouldRollover':
            return self.should_rollover
        if name == 'doRollover':
            return self.do_rollover
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def emit(self, record):
        """Emit a record, handling closed streams gracefully."""
        # Check if stream is usable before attempting to write
        if not _is_stream_usable(self.stream):
            # Try to reopen the stream
            try:
                if self.stream:
                    try:
                        self.stream.close()
                    except (ValueError, OSError):
                        pass
                self.stream = self._open()
            except (ValueError, OSError):
                # Can't reopen, silently ignore
                return

        try:
            super().emit(record)
        except (ValueError, OSError, AttributeError, RuntimeError) as error:
            # Handle "I/O operation on closed file" errors gracefully
            error_str = str(error).lower()
            if any(phrase in error_str for phrase in [
                "closed file", "i/o operation", "bad file descriptor",
                "operation on closed", "stream is closed"
            ]):
                # Stream is closed, try to reopen it
                try:
                    if self.stream:
                        try:
                            self.stream.close()
                        except (ValueError, OSError):
                            pass
                    self.stream = self._open()
                    super().emit(record)
                except (ValueError, OSError, AttributeError, RuntimeError):
                    # If we can't reopen, silently ignore
                    return
            else:
                # Re-raise other errors
                raise
        except Exception:
            # Catch any other unexpected errors to prevent logging failures
            # from crashing the application
            return

    def _cleanup_old_files(self) -> None:
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


def _is_stream_usable(stream) -> bool:
    """
    Check if a stream is usable for logging without triggering errors.

    Returns True if stream can be written to, False otherwise.
    This function is safe to call even if the stream is closed.
    """
    if stream is None:
        return False

    try:
        # Check if stream has 'closed' attribute
        if hasattr(stream, 'closed'):
            if stream.closed:
                return False

        # Check if stream has 'write' method (required for logging)
        if not hasattr(stream, 'write'):
            return False

        # For file-like objects, check if they're in a valid state
        # We don't actually write to avoid side effects, just check attributes
        # The actual write will happen in the handler's emit() method
        return True
    except (AttributeError, ValueError, OSError):
        # Can't determine, assume not usable to be safe
        return False


class SafeStreamHandler(logging.StreamHandler):
    """StreamHandler that gracefully handles closed streams."""

    def emit(self, record):
        """Emit a record, handling closed streams gracefully."""
        if not _is_stream_usable(self.stream):
            return

        try:
            super().emit(record)
        except (ValueError, OSError, AttributeError, RuntimeError) as error:
            # Handle "I/O operation on closed file" errors gracefully
            error_str = str(error).lower()
            if any(phrase in error_str for phrase in [
                "closed file", "i/o operation", "bad file descriptor",
                "operation on closed", "stream is closed"
            ]):
                # Stream is closed, silently ignore
                return
            # Re-raise other errors
            raise
        except Exception:
            # Catch any other unexpected errors to prevent logging failures
            # from crashing the application
            return


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

    def __init__(self, fmt=None, datefmt=None, style: Literal['%', '{', '$'] = '%', validate=True, **_kwargs):
        """
        Initialize formatter, accepting Uvicorn's use_colors parameter.
        We ignore use_colors since we handle our own color logic.
        """
        # Call parent init without use_colors (not a standard logging.Formatter parameter)
        super().__init__(fmt=fmt, datefmt=datefmt, style=style, validate=validate)
        # We manage our own colors in the format() method

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
        pid = os.getpid()

        # Normalize message spacing: strip leading whitespace and normalize multiple spaces to single space
        message = record.getMessage().lstrip()
        message = re.sub(r' +', ' ', message)  # Normalize multiple spaces to single space

        return f"[{timestamp}] {colored_level} | {source} | [{pid}] {message}"


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


class CancelledErrorFilter(logging.Filter):
    """Filter out CancelledError and Windows Proactor errors during graceful shutdown.

    DISABLED: For verbose logging, we show everything.
    """
    def filter(self, record):
        # For verbose logging, show everything - no filtering
        return True


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
            api_name = self._extract_api_name(url)  # pylint: disable=protected-access
            endpoint = self._extract_endpoint(url)  # pylint: disable=protected-access
            return f"{api_name} API: {method} {endpoint} → {status_code} {status_text}"
        return message  # Return original if pattern doesn't match

    def _reformat_request(self, message: str) -> str:
        """Reformat HTTP Request message."""
        # Pattern: "HTTP Request: METHOD URL ..."
        pattern = r'HTTP Request:\s+(\w+)\s+(https?://[^\s]+)'
        match = re.match(pattern, message)
        if match:
            method, url = match.groups()
            api_name = self._extract_api_name(url)  # pylint: disable=protected-access
            endpoint = self._extract_endpoint(url)  # pylint: disable=protected-access
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
            reformatted = self._reformat_response(message)  # pylint: disable=protected-access
            record.msg = reformatted
            record.args = ()
            record._openai_reformatted = True  # pylint: disable=protected-access

        # Reformat HTTP Request messages
        elif message.startswith('HTTP Request:'):
            reformatted = self._reformat_request(message)  # pylint: disable=protected-access
            record.msg = reformatted
            record.args = ()
            record._openai_reformatted = True  # pylint: disable=protected-access

        return True


def setup_logging():
    """
    Configure all logging for the application.
    
    Sets up:
    - Console and file handlers with unified formatter
    - Logger levels and filters
    - Uvicorn logger configuration
    - Frontend logger configuration
    - OpenAI SDK logger configuration
    """
    # Create formatter
    unified_formatter = UnifiedFormatter()

    # Use UTF-8 encoding for console output to handle emojis and Chinese characters
    # Only create console handler if stdout is usable
    # This prevents errors when stdout is closed (e.g., in uvicorn workers or reload mode)
    handlers = []

    if _is_stream_usable(sys.stdout):
        console_handler = SafeStreamHandler(sys.stdout)
        console_handler.setFormatter(unified_formatter)
        handlers.append(console_handler)
    # If stdout is not usable, we'll only use file handler (more reliable)

    # Use custom TimestampedRotatingFileHandler to create timestamped log files every 72 hours
    # Each file is named with the start timestamp: app.YYYY-MM-DD_HH-MM-SS.log
    # File handler is always created as it's more reliable than console streams
    try:
        file_handler = TimestampedRotatingFileHandler(
            os.path.join("logs", "app.log"),
            interval_hours=72,  # Every 72 hours (3 days)
            backup_count=10,  # Keep 10 backup files (30 days of logs)
            encoding="utf-8"
        )
        file_handler.setFormatter(unified_formatter)
        handlers.append(file_handler)
    except (OSError, IOError):
        # If we can't create file handler, at least try to use console if available
        # This is a fallback for edge cases where logs directory can't be created
        if handlers:
            pass  # At least we have console handler
        else:
            # Last resort: create a null handler to prevent errors
            handlers.append(logging.NullHandler())

    # Determine log level - always use DEBUG for full verbose logging
    # Override with VERBOSE_LOGGING env var if set, otherwise default to DEBUG
    if hasattr(config, 'verbose_logging') and config.verbose_logging:
        log_level = logging.DEBUG
    else:
        # Default to DEBUG for full verbose logging
        log_level_str = getattr(config, 'log_level', 'DEBUG')
        log_level = getattr(logging, log_level_str.upper(), logging.DEBUG)

    # Configure logging with available handlers
    # Use force=True to replace any existing configuration
    logging.basicConfig(
        level=logging.DEBUG,  # Always DEBUG for full verbose logging
        handlers=handlers,
        force=True
    )

    # Set all loggers to DEBUG level for full verbose logging
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Set specific loggers to DEBUG
    for logger_name in [
        'services', 'llm_chunking', 'tasks', 'clients', 'agents',
        'routers', 'utils', 'config', 'celery', 'uvicorn'
    ]:
        specific_logger = logging.getLogger(logger_name)
        specific_logger.setLevel(logging.DEBUG)
        specific_logger.propagate = True

    # Configure Uvicorn's loggers to use our custom formatter
    # Note: uvicorn.access is excluded - access_log=False in run_server.py disables HTTP request logging
    for uvicorn_logger_name in ['uvicorn', 'uvicorn.error']:
        uvicorn_logger = logging.getLogger(uvicorn_logger_name)
        uvicorn_logger.handlers = []  # Remove default handlers
        # Only add handlers that were successfully created
        for handler in handlers:
            uvicorn_logger.addHandler(handler)
        uvicorn_logger.addFilter(UvicornInvalidRequestFilter())  # Downgrade invalid request warnings
        uvicorn_logger.propagate = False

    # Create main logger early
    logger = logging.getLogger(__name__)

    # Configure frontend logger to use the same app.log file
    # Frontend logs are tagged with [FRNT] by UnifiedFormatter, so they can be filtered if needed
    frontend_logger = logging.getLogger('frontend')
    frontend_logger.setLevel(logging.DEBUG)  # Always accept all frontend logs
    frontend_logger.handlers = []  # Remove default handlers
    # Only add handlers that were successfully created
    for handler in handlers:
        frontend_logger.addHandler(handler)
    frontend_logger.propagate = False  # Don't propagate to root logger to avoid double logging

    if os.getenv('UVICORN_WORKER_ID') is None:
        logger.debug("Frontend logger configured to write to unified log file: logs/app.log")

    # Suppress asyncio CancelledError and Windows Proactor errors during shutdown
    # DISABLED for verbose logging - show everything
    asyncio_logger = logging.getLogger('asyncio')
    asyncio_logger.addFilter(CancelledErrorFilter())

    # Add filter to main logger
    logger.addFilter(CancelledErrorFilter())

    # Set external HTTP libraries to WARNING by default to reduce verbosity
    # Only show DEBUG/INFO logs when explicitly enabled via HTTP_DEBUG env var
    http_debug_enabled = os.getenv('HTTP_DEBUG', '').lower() in ('1', 'true', 'yes')
    http_level = logging.DEBUG if http_debug_enabled else logging.WARNING

    logging.getLogger('httpx').setLevel(http_level)
    logging.getLogger('httpcore').setLevel(http_level)
    # hpack/h2: HTTP/2 HPACK header compression - very verbose at DEBUG
    logging.getLogger('hpack').setLevel(http_level)
    logging.getLogger('h2').setLevel(http_level)

    # Other external libraries can remain at DEBUG for troubleshooting
    logging.getLogger('qcloud_cos').setLevel(logging.DEBUG)
    logging.getLogger('qcloud_cos.cos_client').setLevel(logging.DEBUG)
    logging.getLogger('qcloud_cos.cos_auth').setLevel(logging.DEBUG)
    logging.getLogger('urllib3').setLevel(logging.DEBUG)
    logging.getLogger('urllib3.connectionpool').setLevel(logging.DEBUG)

    # Enable OpenAI SDK logging for HTTP request/response visibility
    # This provides detailed logs for Hunyuan and Doubao API calls
    # Respect global LOG_LEVEL setting - only show DEBUG logs if LOG_LEVEL=DEBUG
    openai_logger = logging.getLogger('openai')
    openai_logger.setLevel(log_level)  # Use global log level instead of hardcoded DEBUG
    openai_logger.handlers = []  # Remove default handlers
    # Only add handlers that were successfully created
    for handler in handlers:
        openai_logger.addHandler(handler)
    openai_logger.addFilter(OpenAIHTTPLogFilter())
    openai_logger.propagate = False

    # Only log from main process, not each worker
    if os.getenv('UVICORN_WORKER_ID') is None:
        log_level_str = getattr(config, 'LOG_LEVEL', 'DEBUG')
        logger.debug("Logging initialized: %s", log_level_str)

    return logger
