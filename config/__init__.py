"""
Configuration Package

This package contains application configuration:
- Settings: Environment variables and application settings (Config class and config instance)

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from .settings import Config, config

__all__ = [
    'Config',
    'config',
]

