"""
Uvicorn Logging Configuration
==============================

Custom logging configuration for Uvicorn that matches our main.py format.
This ensures ALL logs (including reload messages) use our clean format.

@author lycosa9527
@made_by MindSpring Team
"""

import logging
import sys

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

