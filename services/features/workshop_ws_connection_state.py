"""
Shared in-process state for diagram workshop WebSockets.

Separated from the router so fan-out delivery can run without circular imports.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Dict

from fastapi import WebSocket

ACTIVE_CONNECTIONS: Dict[str, Dict[int, WebSocket]] = {}
ACTIVE_EDITORS: Dict[str, Dict[str, Dict[int, str]]] = {}
