"""
Qdrant startup validation and error helpers.
Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
from urllib.parse import urlparse

import qdrant_client

from services.infrastructure.utils.launch_commands import (
    error_footer_launch_reference,
    lines_qdrant_connection_failed,
)

logger = logging.getLogger(__name__)

# Error message width (matching Redis format)
_ERROR_WIDTH = 70


def parse_qdrant_host_port(qdrant_host: str) -> tuple[str, int]:
    """
    Parse QDRANT_HOST as 'host:port' or bare host (default port 6333).

    Args:
        qdrant_host: Value from QDRANT_HOST environment variable.

    Returns:
        Host string and port number.
    """
    if ":" in qdrant_host:
        host, port_str = qdrant_host.rsplit(":", 1)
        return host, int(port_str)
    return qdrant_host, 6333


class QdrantStartupError(Exception):
    """
    Raised when Qdrant connection fails during startup.

    This is a controlled startup failure - the error message has already
    been logged with instructions. Catching this exception should exit
    cleanly without logging additional tracebacks.
    """


def _log_qdrant_error(title: str, details: list[str]) -> None:
    """
    Log a Qdrant error with clean, professional formatting.

    Args:
        title: Error title (e.g., "QDRANT CONNECTION FAILED")
        details: List of detail lines to display
    """
    separator = "=" * _ERROR_WIDTH

    lines = [
        "",
        separator,
        title.center(_ERROR_WIDTH),
        separator,
        "",
    ]
    lines.extend(details)
    lines.extend(["", separator, ""])

    error_msg = "\n".join(lines)
    logger.critical(error_msg)


def init_qdrant_sync() -> bool:
    """
    Initialize Qdrant connection (synchronous version for startup).

    Qdrant is REQUIRED. Application will exit if connection fails.

    Returns:
        True if Qdrant is available.

    Raises:
        QdrantStartupError: Application will exit if Qdrant is unavailable.
    """
    qdrant_host = os.getenv("QDRANT_HOST", "")
    qdrant_url = os.getenv("QDRANT_URL", "")

    logger.info("[Qdrant] Validating Qdrant connection...")

    # Check if Qdrant is configured
    if not qdrant_url and not qdrant_host:
        _log_qdrant_error(
            title="QDRANT NOT CONFIGURED",
            details=[
                "Qdrant server is not configured.",
                "",
                "Set one of the following in your .env file:",
                "  QDRANT_HOST=localhost:6333",
                "  or",
                "  QDRANT_URL=http://localhost:6333",
                "",
                "Install Qdrant (Linux):",
                "  sudo python3 scripts/setup/setup.py",
                "  (see docs/QDRANT_SETUP.md)",
                "",
                "Or download from: https://github.com/qdrant/qdrant/releases",
                *error_footer_launch_reference(),
            ],
        )
        raise QdrantStartupError("Qdrant not configured") from None

    try:
        # Try to create Qdrant client and verify connection
        if qdrant_url:
            logger.info("[Qdrant] Connecting to %s...", qdrant_url)
            client = qdrant_client.QdrantClient(url=qdrant_url)
        else:
            host, port = parse_qdrant_host_port(qdrant_host)
            logger.info("[Qdrant] Connecting to %s:%s...", host, port)
            client = qdrant_client.QdrantClient(host=host, port=port)

        # Test connection by getting collections (lightweight operation)
        client.get_collections()
        logger.info("[Qdrant] Connected successfully")
        return True

    except Exception as exc:
        connection_info = qdrant_url if qdrant_url else f"{qdrant_host or 'localhost:6333'}"
        if qdrant_url:
            parsed = urlparse(qdrant_url)
            err_port = parsed.port if parsed.port is not None else 6333
        else:
            _, err_port = parse_qdrant_host_port(qdrant_host)
        _log_qdrant_error(
            title="QDRANT CONNECTION FAILED",
            details=lines_qdrant_connection_failed(connection_info, str(exc), err_port),
        )
        raise QdrantStartupError(f"Failed to connect to Qdrant: {exc}") from exc
