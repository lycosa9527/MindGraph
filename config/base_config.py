"""Base configuration class and core settings.

This module provides the base Config class with caching mechanism and core
application settings like version, server configuration, and logging.
"""
import logging
import os
import time
from pathlib import Path
import socket

logger = logging.getLogger(__name__)


class BaseConfig:
    """Base configuration class with caching mechanism."""

    def __init__(self):
        self._cache = {}
        self._cache_timestamp = 0
        self._cache_duration = 30
        self._version = None

    def _get_cached_value(self, key: str, default=None):
        """Get cached value from environment."""
        current_time = time.time()
        if current_time - self._cache_timestamp > self._cache_duration:
            self._cache.clear()
            self._cache_timestamp = current_time
        if key not in self._cache:
            self._cache[key] = os.environ.get(key, default)
        return self._cache[key]

    @property
    def version(self) -> str:
        """
        Application version - read from VERSION file (single source of truth).
        Cached after first read for performance.
        """
        if self._version is None:
            try:
                version_file = Path(__file__).parent.parent / 'VERSION'
                self._version = version_file.read_text().strip()
            except Exception as e:  # pylint: disable=broad-except
                logger.warning("Failed to read VERSION file: %s", e)
                self._version = "0.0.0"
        return self._version

    @property
    def host(self) -> str:
        """FastAPI application host address."""
        return self._get_cached_value('HOST', '0.0.0.0')

    @property
    def port(self) -> int:
        """FastAPI application port number."""
        try:
            val = int(self._get_cached_value('PORT', '9527'))
            if not 1 <= val <= 65535:
                logger.warning("PORT %s out of range, using 9527", val)
                return 9527
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid PORT value, using 9527")
            return 9527

    @property
    def server_url(self) -> str:
        """Get the server URL for static file loading."""
        host = self.host
        port = self.port

        try:
            external_host = os.environ.get('EXTERNAL_HOST')
            if external_host:
                host = external_host
                if os.getenv('UVICORN_WORKER_ID') is None or os.getenv('UVICORN_WORKER_ID') == '0':
                    logger.info("Using EXTERNAL_HOST from environment: %s", external_host)
            else:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                lan_ip = s.getsockname()[0]
                s.close()
                host = lan_ip
                logger.warning("EXTERNAL_HOST not set, using LAN IP: %s", lan_ip)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Failed to determine server IP address for external access: %s", e)
            logger.error("Please set EXTERNAL_HOST environment variable with your server's public IP")
            raise RuntimeError(
                "Cannot determine server IP address for external access. "
                "Please set EXTERNAL_HOST environment variable with your server's public IP address."
            ) from e

        return f"http://{host}:{port}"

    @property
    def debug(self) -> bool:
        """FastAPI debug mode setting."""
        return self._get_cached_value('DEBUG', 'False').lower() == 'true'

    @property
    def log_level(self) -> str:
        """Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)."""
        level = self._get_cached_value('LOG_LEVEL', 'INFO').upper()
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if level not in valid_levels:
            logger.warning("Invalid LOG_LEVEL '%s', using INFO", level)
            return 'INFO'
        return level

    @property
    def verbose_logging(self) -> bool:
        """Enable verbose logging for debugging (logs all user interactions)."""
        return self._get_cached_value('VERBOSE_LOGGING', 'False').lower() == 'true'
