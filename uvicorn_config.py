"""
Uvicorn Configuration for MindGraph FastAPI Application
=======================================================

Unified configuration file combining server settings and logging configuration.
Production-ready async server configuration for Windows + Ubuntu deployment.

@author lycosa9527
@made_by MindSpring Team
"""

import os
import sys
import logging
import multiprocessing

# ============================================================================
# SERVER CONFIGURATION
# ============================================================================

# Host and Port
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
host = "0.0.0.0"
port = int(os.getenv('PORT', '5000'))

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
timeout_keep_alive = 300  # 5 minutes for SSE connections
timeout_graceful_shutdown = 10  # Reduced to 10s for faster shutdown (was 30s)

# Connection limits to prevent shutdown hangs
limit_concurrency = 1000  # Max concurrent connections per worker

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
    
    def __init__(self, fmt=None, datefmt=None, style='%', validate=True, use_colors=None):
        """
        Initialize formatter, accepting Uvicorn's use_colors parameter.
        We ignore use_colors since we handle our own color logic.
        """
        # Call parent init without use_colors (not a standard logging.Formatter parameter)
        super().__init__(fmt=fmt, datefmt=datefmt, style=style, validate=validate)
        # We manage our own colors in the format() method
    
    def format(self, record):
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
        
        return f"[{timestamp}] {colored_level} | {source} | {record.getMessage()}"


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
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
        "access": {
            "class": "logging.StreamHandler",
            "formatter": "access",
            "stream": "ext://sys.stdout",
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
log_level = os.getenv('LOG_LEVEL', 'info').lower()

# Access log
access_log = True
use_colors = True

# Reload on code changes (development only)
reload = os.getenv('ENVIRONMENT', 'production') == 'development'

# Production settings
if os.getenv('ENVIRONMENT') == 'production':
    # Disable auto-reload in production
    reload = False
    
    # Use production log level
    log_level = 'warning'

# ============================================================================
# CONFIGURATION SUMMARY
# ============================================================================

config_summary = f"""
Uvicorn Configuration Summary:
------------------------------
Host: {host}
Port: {port}
Workers: {workers} (async - each handles 1000s of connections)
Timeout Keep-Alive: {timeout_keep_alive}s
Graceful Shutdown: {timeout_graceful_shutdown}s
Log Level: {log_level}
Reload: {reload}
Environment: {os.getenv('ENVIRONMENT', 'production')}

Expected Capacity: 4,000+ concurrent SSE connections per worker
Total Capacity: ~{workers * 4000} concurrent connections
"""

if __name__ == "__main__":
    print(config_summary)

