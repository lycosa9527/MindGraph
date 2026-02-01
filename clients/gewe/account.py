"""Account Management Module.

Handles login, logout, and account status operations.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, Optional, Protocol


class _GeweClientProtocol(Protocol):
    """Protocol defining the interface expected by AccountMixin"""
    token: str

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Gewe API"""
        raise NotImplementedError


class AccountMixin:
    """Mixin for account management APIs"""

    async def get_login_qr_code(
        self: "_GeweClientProtocol",
        app_id: str = "",
        region_id: str = "320000",
        device_type: str = "mac",
        proxy_ip: Optional[str] = None,
        ttuid: Optional[str] = None,
        aid: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get login QR code (Step 1).

        Args:
            app_id: Device ID (empty for first login)
            region_id: Region ID (default: 320000 for Jiangsu)
            device_type: Device type: "ipad" (recommended) or "mac"
            proxy_ip: Custom proxy IP (format: socks5://username:password@123.2.2.2:8932)
            ttuid: Proxy ID download URL
            aid: Aid download URL (local computer proxy)

        Returns:
            Response containing qrImgBase64 and uuid
        """
        payload = {
            "appId": app_id,
            "regionId": region_id,
            "type": device_type
        }
        if proxy_ip:
            payload["proxyIp"] = proxy_ip
        if ttuid:
            payload["ttuid"] = ttuid
        if aid:
            payload["aid"] = aid

        return await self._request("POST", "/gewe/v2/api/login/getLoginQrCode", json_data=payload)

    async def check_login(
        self: "_GeweClientProtocol",
        app_id: str,
        uuid: str,
        auto_sliding: bool = False,
        proxy_ip: Optional[str] = None,
        captch_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check login status (Step 2).

        Args:
            app_id: Device ID
            uuid: UUID from get_login_qr_code response
            auto_sliding: Auto sliding verification (for mac, default: False)
            proxy_ip: Proxy IP
            captch_code: Captcha code if required

        Returns:
            Login info including appId and wxid if successful
        """
        payload = {
            "appId": app_id,
            "uuid": uuid,
            "autoSliding": auto_sliding
        }
        if proxy_ip:
            payload["proxyIp"] = proxy_ip
        if captch_code:
            payload["captchCode"] = captch_code

        return await self._request("POST", "/gewe/v2/api/login/checkLogin", json_data=payload)

    async def dialog_login(
        self: "_GeweClientProtocol",
        app_id: str,
        region_id: str = "320000",
        proxy_ip: Optional[str] = None,
        aid: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dialog login (popup confirmation on phone).

        Args:
            app_id: Device ID
            region_id: Region ID
            proxy_ip: Proxy IP
            aid: Aid download URL

        Returns:
            Response with login status
        """
        payload = {
            "appId": app_id,
            "regionId": region_id
        }
        if proxy_ip:
            payload["proxyIp"] = proxy_ip
        if aid:
            payload["aid"] = aid

        return await self._request("POST", "/gewe/v2/api/login/dialogLogin", json_data=payload)

    async def set_callback(
        self: "_GeweClientProtocol",
        callback_url: str
    ) -> Dict[str, Any]:
        """
        Set callback URL for receiving messages.

        Args:
            callback_url: Callback URL to receive messages (HTTP POST/JSON)

        Returns:
            Response confirming callback setup
        """
        payload = {
            "token": self.token,
            "callbackUrl": callback_url
        }
        return await self._request("POST", "/gewe/v2/api/login/setCallback", json_data=payload)

    async def reconnection(
        self: "_GeweClientProtocol",
        app_id: str
    ) -> Dict[str, Any]:
        """
        Reconnect when account is offline.

        Args:
            app_id: Device ID

        Returns:
            Reconnection status
        """
        payload = {"appId": app_id}
        return await self._request("POST", "/gewe/v2/api/login/reconnection", json_data=payload)

    async def login_by_account(
        self: "_GeweClientProtocol",
        app_id: str,
        account: str,
        password: str,
        region_id: str,
        step: int,
        proxy_ip: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Login by account and password (2-step process).

        Step 1: Get appId and QR code (step=1)
        Step 2: Complete login after scanning QR code (step=2)

        Args:
            app_id: Device ID (empty string for step 1)
            account: WeChat account
            password: WeChat password
            region_id: Region ID
            step: Login step (1: get QR code, 2: complete login)
            proxy_ip: Optional proxy IP

        Returns:
            Response with appId and QR code (step 1) or login status (step 2)
        """
        payload = {
            "appId": app_id,
            "account": account,
            "password": password,
            "regionId": region_id,
            "step": step
        }
        if proxy_ip:
            payload["proxyIp"] = proxy_ip

        return await self._request("POST", "/gewe/v2/api/login/loginByAccount", json_data=payload)

    async def check_online(
        self: "_GeweClientProtocol",
        app_id: str
    ) -> Dict[str, Any]:
        """
        Check if account is online.

        Args:
            app_id: Device ID

        Returns:
            Response with online status (data=true means online)
        """
        payload = {"appId": app_id}
        return await self._request("POST", "/gewe/v2/api/login/checkOnline", json_data=payload)

    async def logout(
        self: "_GeweClientProtocol",
        app_id: str
    ) -> Dict[str, Any]:
        """
        Logout.

        Args:
            app_id: Device ID

        Returns:
            Response with operation status
        """
        payload = {"appId": app_id}
        return await self._request("POST", "/gewe/v2/api/login/logout", json_data=payload)
