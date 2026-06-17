"""Process-local registries for Kitty voice (importable without loading HTTP routers).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Any, Dict, List

from fastapi import WebSocket

logger = logging.getLogger("VOICE")

voice_sessions: Dict[str, Dict[str, Any]] = {}

active_websockets: Dict[str, List[WebSocket]] = {}
