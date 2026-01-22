"""
Uvicorn Configuration for MindGraph FastAPI Application
=======================================================

Unified configuration file combining server settings and logging configuration.
Production-ready async server configuration for Windows + Ubuntu deployment.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import os
import sys
import logging
import multiprocessing
from typing import Literal, cast, Any

# Import SafeStreamHandler to handle closed streams gracefully
try:
    from services.infrastructure.utils.logging_config import SafeStreamHandler, _is_stream_usable
except ImportError:
    # Fallback if import fails (shouldn't happen in normal operation)
    SafeStreamHandler = logging.StreamHandler
    def _is_stream_usable(stream):
        """Fallback check for stream usability."""
        if stream is None:
            return False
        try:
            if hasattr(stream, 'closed') and stream.closed:
                return False
            return hasattr(stream, 'write')
        except (AttributeError, ValueError, OSError):
            return False


class SafeStdoutHandler(SafeStreamHandler):
    """SafeStreamHandler that uses stdout, falling back to stderr if stdout is closed."""
    
    def __init__(self, stream=None):
        """Initialize handler with safe stream selection."""
        if stream is None:
            # Use stdout if available, otherwise fall back to stderr
            stream = sys.stdout if _is_stream_usable(sys.stdout) else sys.stderr
        super().__init__(stream)

# ============================================================================
# SERVER CONFIGURATION
# ============================================================================

# Host and Port
BIND = f"0.0.0.0:{os.getenv('PORT', '5000')}"
HOST = "0.0.0.0"
PORT = int(os.getenv('PORT', '5000'))

# Workers (async, so we need FAR fewer than sync servers)
# Formula: 1-2 workers per CPU core (async handles 1000s per worker)
# Default: Number of CPU cores (not 2x+1 like sync servers)
workers = int(os.getenv('UVICORN_WORKERS', multiprocessing.cpu_count()))

# ============================================================================
# ASYNC CONFIGURATION FOR 4,000+ CONCURRENT SSE CONNECTIONS
# ============================================================================

# Uvicorn automatically handles concurrent requests with asyncio event loop
# No thread pool needed - async/await handles concurrency

# Timeout for long-running requests (SSE can run indefinitely)
TIMEOUT_KEEP_ALIVE = 300
TIMEOUT_GRACEFUL_SHUTDOWN = 10

# Connection limits to prevent shutdown hangs
LIMIT_CONCURRENCY = 1000

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Copy of our UnifiedFormatter from main.py
class UnifiedFormatter(logging.Formatter):
    """
    Unified formatter that matches main.py's format.
    Clean, professional logging for both app and Uvicorn.
    """

    COLORS = {
        'DEBUG': '\033[37m',      # Gray
        'INFO': '\033[36m',       # Cyan
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m',
        'BOLD': '\033[1m'
    }

    def __init__(self, fmt=None, datefmt=None, style: Literal['%', '{', '"'] = '%', validate=True, use_colors=None, _use_colors=None):
        """
        Initialize formatter, accepting Uvicorn's use_colors parameter.
        We ignore use_colors since we handle our own color logic.
        """
        # Call parent init without use_colors (not a standard logging.Formatter parameter)
        # Cast style to satisfy type checker (logging uses private _FormatStyle type)
        style_cast = cast(Any, style)
        super().__init__(fmt=fmt, datefmt=datefmt, style=style_cast, validate=validate)
        # We manage our own colors in the format() method

    def format(self, record) -> str:
        # Timestamp: HH:MM:SS
        timestamp = self.formatTime(record, '%H:%M:%S')

        # Level abbreviation
        level_name = record.levelname
        if level_name == 'CRITICAL':
            level_name = 'CRIT'
        elif level_name == 'WARNING':
            level_name = 'WARN'

        color = self.COLORS.get(level_name, '')
        reset = self.COLORS['RESET']

        if level_name == 'CRIT':
            colored_level = f"{self.COLORS['BOLD']}{color}{level_name.ljust(5)}{reset}"
        else:
            colored_level = f"{color}{level_name.ljust(5)}{reset}"

        # Source abbreviation
        source = record.name
        if source.startswith('uvicorn.error'):
            source = 'SRVR'
        elif source.startswith('uvicorn.access'):
            source = 'HTTP'
        elif source.startswith('watchfiles'):
            source = 'WATC'  # File watcher
        elif source.startswith('uvicorn'):
            source = 'SRVR'
        else:
            source = source[:4].upper()

        source = source.ljust(4)

        # Add process ID to identify worker
        pid = os.getpid()

        return f"[{timestamp}] {colored_level} | {source} | [{pid}] {record.getMessage()}"


# Uvicorn logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": UnifiedFormatter,
        },
        "access": {
            "()": UnifiedFormatter,
        },
        "unified": {
            "()": UnifiedFormatter,
        },
    },
    "handlers": {
        "default": {
            "()": SafeStdoutHandler,
            "formatter": "default",
        },
        "access": {
            "()": SafeStdoutHandler,
            "formatter": "access",
        },
    },
    "loggers": {
        "uvicorn": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.error": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.access": {
            "handlers": ["access"],
            "level": "INFO",
            "propagate": False,
        },
        "watchfiles": {
            "handlers": ["default"],
            "level": "WARNING",  # Suppress INFO logs to prevent spam from file changes
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["default"],
        "level": "INFO",
    },
}

# ============================================================================
# DEVELOPMENT VS PRODUCTION
# ============================================================================

# Log level
LOG_LEVEL = os.getenv('LOG_LEVEL', 'info').lower()

# Access log
ACCESS_LOG = True

# Reload on code changes (development only)
RELOAD = os.getenv('ENVIRONMENT', 'production') == 'development'

# Production settings
if os.getenv('ENVIRONMENT') == 'production':
    # Disable auto-reload in production
    RELOAD = False

    # Use production log level
    LOG_LEVEL = 'warning'

# ============================================================================
# CONFIGURATION SUMMARY
# ============================================================================

config_summary = f"""
Uvicorn Configuration Summary:
------------------------------
Host: {HOST}
Port: {PORT}
Workers: {workers} (async - each handles 1000s of connections)
Timeout Keep-Alive: {TIMEOUT_KEEP_ALIVE}s
Graceful Shutdown: {TIMEOUT_GRACEFUL_SHUTDOWN}s
Log Level: {LOG_LEVEL}
Reload: {RELOAD}
Environment: {os.getenv('ENVIRONMENT', 'production')}

Expected Capacity: 4,000+ concurrent SSE connections per worker
Total Capacity: ~{workers * 4000} concurrent connections
"""

if __name__ == "__main__":
    print(config_summary)
