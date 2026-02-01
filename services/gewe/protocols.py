"""Protocol definitions for Gewe Service mixins.

Defines the interface that mixins expect from the base service class.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from abc import ABC, abstractmethod
from typing import Optional, Set, TYPE_CHECKING
from clients.gewe import AsyncGeweClient
from clients.dify import AsyncDifyClient

if TYPE_CHECKING:
    from services.gewe.message_db import GeweMessageDB
    from services.gewe.contact_db import GeweContactDB
    from services.gewe.group_member_db import GeweGroupMemberDB


class GeweServiceBase(ABC):
    """Abstract base class defining methods that mixins expect"""

    _gewe_client: Optional[AsyncGeweClient]
    _dify_client: Optional[AsyncDifyClient]
    _processed_messages: Set[str]
    _message_db: "GeweMessageDB"
    _contact_db: "GeweContactDB"
    _group_member_db: "GeweGroupMemberDB"

    @abstractmethod
    def _get_gewe_client(self) -> AsyncGeweClient:
        """Get or create Gewe client"""

    @abstractmethod
    def _get_dify_client(self) -> AsyncDifyClient:
        """Get or create Dify client"""

    @abstractmethod
    def _save_login_info(self, app_id: str, wxid: str) -> None:
        """Save login info to JSON file"""

    @abstractmethod
    def _load_login_info(self) -> Optional[dict]:
        """Load login info from JSON file"""
