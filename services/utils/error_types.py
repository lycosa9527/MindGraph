"""Reusable exception groupings for narrow ``except`` clauses."""

from __future__ import annotations

import json
from typing import Tuple, Type


class _FallbackRedisError(ConnectionError):
    """Stand-in when redis is not installed."""


class _FallbackSQLAlchemyError(RuntimeError):
    """Stand-in when sqlalchemy is not installed."""


class _FallbackQdrantUnexpectedResponse(RuntimeError):
    """Stand-in when qdrant_client is not installed."""


try:
    from redis.exceptions import RedisError
except ImportError:
    RedisError = _FallbackRedisError

try:
    from sqlalchemy.exc import SQLAlchemyError
except ImportError:
    SQLAlchemyError = _FallbackSQLAlchemyError

try:
    from qdrant_client.http.exceptions import UnexpectedResponse as QdrantUnexpectedResponse
except ImportError:
    QdrantUnexpectedResponse = _FallbackQdrantUnexpectedResponse

# Redis sync/async clients and cache layers
REDIS_ERRORS: Tuple[Type[Exception], ...] = (
    RedisError,
    ConnectionError,
    TimeoutError,
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
)

# JSON / message parsing
JSON_PARSE_ERRORS: Tuple[Type[Exception], ...] = (
    json.JSONDecodeError,
    TypeError,
    ValueError,
    UnicodeDecodeError,
)

# SQLAlchemy database operations
DATABASE_ERRORS: Tuple[Type[Exception], ...] = (
    SQLAlchemyError,
    ConnectionError,
    TimeoutError,
    OSError,
    RuntimeError,
    ValueError,
)

# Local file I/O
FILE_IO_ERRORS: Tuple[Type[Exception], ...] = (
    OSError,
    PermissionError,
    FileNotFoundError,
    IsADirectoryError,
    RuntimeError,
    ValueError,
)

# Background best-effort tasks (log and swallow only expected infra failures)
BACKGROUND_INFRA_ERRORS: Tuple[Type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
)

try:
    import psycopg2
except ImportError:
    _Psycopg2Error = _FallbackSQLAlchemyError
else:
    _Psycopg2Error = psycopg2.Error

# psycopg2 connection and server errors (OperationalError, etc.)
PG_CONNECT_ERRORS: Tuple[Type[Exception], ...] = (
    _Psycopg2Error,
    ConnectionError,
    TimeoutError,
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
)

# LLM agent pipelines, HTTP clients, and provider wrappers
LLM_PIPELINE_ERRORS: Tuple[Type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
    KeyError,
    IndexError,
    UnicodeDecodeError,
)

# Qdrant vector store operations
QDRANT_ERRORS: Tuple[Type[Exception], ...] = (
    QdrantUnexpectedResponse,
    ConnectionError,
    TimeoutError,
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
)

# Script and subprocess HTTP client calls
HTTP_CLIENT_ERRORS: Tuple[Type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
    UnicodeDecodeError,
)
