"""Base Gewe Service.

Provides core service functionality, client management, and utilities.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional, Set
import logging
import os
import json
from pathlib import Path
from sqlalchemy.orm import Session

from clients.gewe import AsyncGeweClient
from clients.dify import AsyncDifyClient

from services.gewe.account import AccountServiceMixin
from services.gewe.message import MessageServiceMixin
from services.gewe.download import DownloadServiceMixin
from services.gewe.group import GroupServiceMixin
from services.gewe.contact import ContactServiceMixin
from services.gewe.personal import PersonalServiceMixin
from services.gewe.tag import TagServiceMixin
from services.gewe.collection import CollectionServiceMixin
from services.gewe.sns import SNSServiceMixin
from services.gewe.video_channel import VideoChannelServiceMixin
from services.gewe.message_db import GeweMessageDB
from services.gewe.contact_db import GeweContactDB
from services.gewe.group_member_db import GeweGroupMemberDB


logger = logging.getLogger(__name__)

GEWE_LOGIN_INFO_PATH = Path("data/gewe_login_info.json")
GEWE_PREFERENCES_PATH = Path("data/gewe_preferences.json")


class GeweService(
    AccountServiceMixin,
    MessageServiceMixin,
    DownloadServiceMixin,
    GroupServiceMixin,
    ContactServiceMixin,
    PersonalServiceMixin,
    TagServiceMixin,
    CollectionServiceMixin,
    SNSServiceMixin,
    VideoChannelServiceMixin
):
    """Service for managing Gewe WeChat integration"""

    def __init__(self, db: Session):
        """
        Initialize Gewe service.

        Args:
            db: Database session
        """
        self.db = db
        self._gewe_client: Optional[AsyncGeweClient] = None
        self._dify_client: Optional[AsyncDifyClient] = None
        self._processed_messages: Set[str] = set()
        self._message_db = GeweMessageDB(db)
        self._contact_db = GeweContactDB(db)
        self._group_member_db = GeweGroupMemberDB(db)
        GEWE_LOGIN_INFO_PATH.parent.mkdir(parents=True, exist_ok=True)
        GEWE_PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)

    def _get_gewe_client(self) -> AsyncGeweClient:
        """Get or create Gewe client"""
        if self._gewe_client is None:
            token = os.getenv('GEWE_TOKEN', '').strip()
            base_url = os.getenv('GEWE_BASE_URL', 'http://api.geweapi.com').strip()
            timeout = int(os.getenv('GEWE_TIMEOUT', '30'))

            if not token:
                logger.error(
                    "GEWE_TOKEN not configured in environment. "
                    "Please check: 1) .env file exists, "
                    "2) GEWE_TOKEN is set, "
                    "3) Server was restarted after adding token"
                )
                raise ValueError("GEWE_TOKEN not configured in environment")

            self._gewe_client = AsyncGeweClient(token=token, base_url=base_url, timeout=timeout)
        return self._gewe_client

    async def cleanup(self):
        """Cleanup resources (close HTTP sessions)"""
        if self._gewe_client:
            try:
                await self._gewe_client.close()
            except Exception as e:
                logger.warning("Error during Gewe client cleanup: %s", e, exc_info=True)
            finally:
                self._gewe_client = None
        if self._dify_client:
            pass

    def _get_dify_client(self) -> AsyncDifyClient:
        """Get or create Dify client"""
        if self._dify_client is None:
            api_key = os.getenv('DIFY_API_KEY')
            api_url = os.getenv('DIFY_API_URL', 'https://api.dify.ai/v1')
            timeout = int(os.getenv('DIFY_TIMEOUT', '30'))

            if not api_key:
                raise ValueError("DIFY_API_KEY not configured in environment")

            self._dify_client = AsyncDifyClient(api_key=api_key, api_url=api_url, timeout=timeout)
        return self._dify_client

    def _save_login_info(self, app_id: str, wxid: str) -> None:
        """Save login info (app_id and wxid) to JSON file."""
        try:
            login_info = {
                "app_id": app_id,
                "wxid": wxid
            }
            with open(GEWE_LOGIN_INFO_PATH, 'w', encoding='utf-8') as f:
                json.dump(login_info, f, indent=2, ensure_ascii=False)
            logger.info("Saved gewe login info: app_id=%s, wxid=%s", app_id, wxid)
        except Exception as e:
            logger.error("Error saving gewe login info: %s", e, exc_info=True)

    def _load_login_info(self) -> Optional[dict]:
        """Load login info (app_id and wxid) from JSON file."""
        try:
            if not GEWE_LOGIN_INFO_PATH.exists():
                return None
            with open(GEWE_LOGIN_INFO_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error("Error loading gewe login info: %s", e, exc_info=True)
            return None

    def reset_device_id(self) -> None:
        """
        Reset device ID by deleting the login info file.
        
        This clears the saved app_id and wxid. On next login (QR code scan),
        the Gewe API will generate new app_id and wxid automatically.
        """
        try:
            if GEWE_LOGIN_INFO_PATH.exists():
                GEWE_LOGIN_INFO_PATH.unlink()
                logger.info("Reset device ID: deleted login info file (app_id and wxid cleared)")
            else:
                logger.info("Reset device ID: login info file does not exist")
        except Exception as e:
            logger.error("Error resetting device ID: %s", e, exc_info=True)
            raise

    def save_preferences(self, region_id: str, device_type: str) -> None:
        """Save user preferences (region_id and device_type) to JSON file."""
        try:
            preferences = {
                "region_id": region_id,
                "device_type": device_type
            }
            with open(GEWE_PREFERENCES_PATH, 'w', encoding='utf-8') as f:
                json.dump(preferences, f, indent=2, ensure_ascii=False)
            logger.info("Saved gewe preferences: region_id=%s, device_type=%s", region_id, device_type)
        except Exception as e:
            logger.error("Error saving gewe preferences: %s", e, exc_info=True)

    def get_preferences(self) -> dict:
        """Load user preferences (region_id and device_type) from JSON file."""
        try:
            if not GEWE_PREFERENCES_PATH.exists():
                return {
                    "region_id": "110000",
                    "device_type": "ipad"
                }
            with open(GEWE_PREFERENCES_PATH, 'r', encoding='utf-8') as f:
                preferences = json.load(f)
            return {
                "region_id": preferences.get("region_id", "110000"),
                "device_type": preferences.get("device_type", "ipad")
            }
        except Exception as e:
            logger.error("Error loading gewe preferences: %s", e, exc_info=True)
            return {
                "region_id": "110000",
                "device_type": "ipad"
            }

    async def close(self):
        """Close client connections"""
        if self._gewe_client:
            await self._gewe_client.close()
