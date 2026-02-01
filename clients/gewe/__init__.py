"""Gewe WeChat API Client Module.

Modular client for interacting with Gewe WeChat API.
Organized by functional modules matching API documentation structure.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from clients.gewe.base import AsyncGeweClient, GeweAPIError

__all__ = ['AsyncGeweClient', 'GeweAPIError']
