"""
Internal Services Package

This package contains internal services:
- Browser: Playwright-based browser automation for PNG export
"""

from .browser import BrowserContextManager

__all__ = [
    'BrowserContextManager',
]

