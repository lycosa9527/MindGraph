"""
Configuration Package

This package contains application configuration:
- Settings: Environment variables and application settings (Config class and config instance)
"""

from .settings import Config, config

__all__ = [
    'Config',
    'config',
]

