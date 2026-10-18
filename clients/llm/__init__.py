"""
LLM client classes.

Instances are created by ``ClientManager`` during application startup.
This package does not construct clients on import.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from clients.llm.dashscope import DeepSeekClient, KimiClient, QwenClient
from clients.llm.http_client_manager import close_httpx_clients
from clients.llm.volcengine import VolcengineClient

__all__ = [
    "QwenClient",
    "DeepSeekClient",
    "KimiClient",
    "VolcengineClient",
    "close_httpx_clients",
]
