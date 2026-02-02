"""Account Service Module.

Handles account-related service operations: login, logout, preferences.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, Optional
import logging

from services.gewe.protocols import GeweServiceBase

logger = logging.getLogger(__name__)


class AccountServiceMixin(GeweServiceBase):
    """Mixin for account-related service methods"""

    async def get_login_qr_code(
        self,
        app_id: str = "",
        region_id: str = "320000",
        device_type: str = "mac",
        proxy_ip: Optional[str] = None,
        ttuid: Optional[str] = None,
        aid: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get login QR code."""
        client = self._get_gewe_client()
        return await client.get_login_qr_code(
            app_id=app_id,
            region_id=region_id,
            device_type=device_type,
            proxy_ip=proxy_ip,
            ttuid=ttuid,
            aid=aid
        )

    async def check_login(
        self,
        app_id: str,
        uuid: str,
        auto_sliding: bool = False,
        proxy_ip: Optional[str] = None,
        captch_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check login status. Saves app_id and wxid on successful login."""
        client = self._get_gewe_client()
        result = await client.check_login(
            app_id=app_id,
            uuid=uuid,
            auto_sliding=auto_sliding,
            proxy_ip=proxy_ip,
            captch_code=captch_code
        )

        if result.get('ret') == 200:
            data = result.get('data', {})
            if isinstance(data, dict):
                status = data.get('status')
                if status == 2:
                    login_info = data.get('loginInfo', {})
                    if isinstance(login_info, dict):
                        wxid = login_info.get('wxid', '')
                        login_app_id = data.get('appId') or app_id
                        if login_app_id and wxid:
                            self._save_login_info(login_app_id, wxid)
                            logger.info("Login successful, saved app_id=%s, wxid=%s", login_app_id, wxid)
                    else:
                        wxid = data.get('wxid') or data.get('Wxid') or data.get('wxId', '')
                        login_app_id = data.get('appId') or app_id
                        if login_app_id and wxid:
                            self._save_login_info(login_app_id, wxid)
                            logger.info("Login successful (fallback), saved app_id=%s, wxid=%s", login_app_id, wxid)

        return result

    def get_saved_login_info(self) -> Optional[Dict[str, str]]:
        """Get saved login info."""
        return self._load_login_info()


    async def set_callback(
        self,
        callback_url: str
    ) -> Dict[str, Any]:
        """Set callback URL for receiving messages."""
        client = self._get_gewe_client()
        return await client.set_callback(callback_url=callback_url)

    async def login_by_account(
        self,
        app_id: str,
        account: str,
        password: str,
        region_id: str,
        step: int,
        proxy_ip: Optional[str] = None
    ) -> Dict[str, Any]:
        """Login by account and password (2-step process)."""
        client = self._get_gewe_client()
        return await client.login_by_account(
            app_id=app_id,
            account=account,
            password=password,
            region_id=region_id,
            step=step,
            proxy_ip=proxy_ip
        )

    async def check_online(
        self,
        app_id: str
    ) -> Dict[str, Any]:
        """Check if account is online."""
        client = self._get_gewe_client()
        return await client.check_online(app_id=app_id)

    async def logout(
        self,
        app_id: str
    ) -> Dict[str, Any]:
        """Logout."""
        client = self._get_gewe_client()
        return await client.logout(app_id=app_id)
