"""
Shared HTTP/WebSocket connection types for auth and geo middleware.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Union

from fastapi import Request, WebSocket

HttpOrWebSocket = Union[Request, WebSocket]
