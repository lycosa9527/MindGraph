"""
Internal Services Package

This package contains internal services:
- Browser: Playwright-based browser automation for PNG export
- LLM Service: Centralized LLM client management and orchestration

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from .browser import BrowserContextManager

# LLM Service imports (Phases 1-4 complete)
from .llm_service import llm_service
from .client_manager import client_manager
from .error_handler import error_handler
from .prompt_manager import prompt_manager
from .performance_tracker import performance_tracker

__all__ = [
    'BrowserContextManager',
    'llm_service',
    'client_manager',
    'error_handler',
    'prompt_manager',
    'performance_tracker',
]

