"""
Maite domain errors.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations


class MaiteConflictError(ValueError):
    """Raised when a session action conflicts with current state (HTTP 409)."""


class MaiteNotFoundError(ValueError):
    """Raised when a Maite resource is missing (HTTP 404)."""


class MaiteForbiddenError(ValueError):
    """Raised when the caller does not own the resource (HTTP 403)."""
