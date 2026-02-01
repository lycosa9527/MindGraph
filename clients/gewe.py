"""Gewe WeChat API Client for FastAPI MindGraph Application.

DEPRECATED: This file is kept for backward compatibility.
Please use the modular structure: from clients.gewe import AsyncGeweClient

The client has been refactored into modules:
- clients.gewe.base - Base client
- clients.gewe.account - Account management
- clients.gewe.message - Message sending
- clients.gewe.download - Message download
- clients.gewe.group - Group management
- clients.gewe.contact - Contact management
- clients.gewe.enterprise - Enterprise WeChat
- clients.gewe.sns - Social Network/Moments
- clients.gewe.personal - Personal/Profile

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
# Re-export from new modular structure for backward compatibility
from clients.gewe.base import AsyncGeweClient, GeweAPIError

__all__ = ['AsyncGeweClient', 'GeweAPIError']
