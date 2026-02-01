"""Gewe WeChat Service.

DEPRECATED: This file is kept for backward compatibility.
Please use the modular structure: from services.gewe import GeweService

The service has been refactored into modules:
- services.gewe.base - Base service
- services.gewe.account - Account service
- services.gewe.message - Message service (with Dify integration)
- services.gewe.download - Download service
- services.gewe.group - Group service
- services.gewe.contact - Contact service
- services.gewe.personal - Personal service

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
# Re-export from new modular structure for backward compatibility
from services.gewe.base import GeweService

__all__ = ['GeweService']
