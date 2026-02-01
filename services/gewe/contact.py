"""Contact Service Module.

Handles contact/friend-related service operations with database caching.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, Optional, List, TYPE_CHECKING
import logging

from services.gewe.protocols import GeweServiceBase

if TYPE_CHECKING:
    from services.gewe.contact_db import GeweContactDB

logger = logging.getLogger(__name__)


class ContactServiceMixin(GeweServiceBase):
    """Mixin for contact-related service methods"""

    _contact_db: "GeweContactDB"

    async def get_contacts_list(
        self,
        app_id: str
    ) -> Dict[str, Any]:
        """
        Get contacts list from API and cache in database.

        Args:
            app_id: Gewe app ID

        Returns:
            API response with contacts list
        """
        client = self._get_gewe_client()
        response = await client.fetch_contacts_list(app_id=app_id)

        # Cache contacts in database
        if response and response.get("code") == 0:
            contacts = response.get("data", {}).get("contacts", [])
            if contacts:
                try:
                    saved_count = self._contact_db.save_contacts_batch(
                        app_id=app_id,
                        contacts=contacts
                    )
                    logger.info("Cached %d contacts for app %s", saved_count, app_id)
                except Exception as e:
                    logger.warning("Failed to cache contacts: %s", e)

        return response

    def get_cached_contact(
        self,
        app_id: str,
        wxid: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get contact from cache.

        Args:
            app_id: Gewe app ID
            wxid: Contact wxid

        Returns:
            Contact dictionary or None if not cached
        """
        return self._contact_db.get_contact(app_id=app_id, wxid=wxid)

    def get_cached_contacts(
        self,
        app_id: str,
        contact_type: Optional[str] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get contacts from cache.

        Args:
            app_id: Gewe app ID
            contact_type: Filter by type (friend, group, official)
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            List of contact dictionaries
        """
        return self._contact_db.get_contacts(
            app_id=app_id,
            contact_type=contact_type,
            offset=offset,
            limit=limit
        )

    async def get_contacts_info(
        self,
        app_id: str,
        wxids: list
    ) -> Dict[str, Any]:
        """Get brief info for contacts."""
        client = self._get_gewe_client()
        return await client.get_brief_info(app_id=app_id, wxids=wxids)

    async def search_contacts(
        self,
        app_id: str,
        contacts_info: str
    ) -> Dict[str, Any]:
        """Search contacts."""
        client = self._get_gewe_client()
        return await client.search_contacts(
            app_id=app_id,
            contacts_info=contacts_info
        )

    async def add_contacts(
        self,
        app_id: str,
        scene: int,
        option: int,
        v3: str,
        v4: str,
        content: str
    ) -> Dict[str, Any]:
        """Add contact or agree to friend request."""
        client = self._get_gewe_client()
        return await client.add_contacts(
            app_id=app_id,
            scene=scene,
            option=option,
            v3=v3,
            v4=v4,
            content=content
        )

    async def delete_friend(
        self,
        app_id: str,
        wxid: str
    ) -> Dict[str, Any]:
        """Delete friend."""
        client = self._get_gewe_client()
        return await client.delete_friend(
            app_id=app_id,
            wxid=wxid
        )

    async def check_friend_relationship(
        self,
        app_id: str,
        wxids: list
    ) -> Dict[str, Any]:
        """Check friend relationship."""
        client = self._get_gewe_client()
        return await client.check_friend_relationship(
            app_id=app_id,
            wxids=wxids
        )
