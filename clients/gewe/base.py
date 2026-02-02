"""Base Gewe Client.

Provides core HTTP client functionality and base classes.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, Optional
import logging
import aiohttp

from clients.gewe.account import AccountMixin
from clients.gewe.message import MessageMixin
from clients.gewe.download import DownloadMixin
from clients.gewe.group import GroupMixin
from clients.gewe.contact import ContactMixin
from clients.gewe.enterprise import EnterpriseMixin
from clients.gewe.sns import SNSMixin
from clients.gewe.personal import PersonalMixin
from clients.gewe.tag import TagMixin
from clients.gewe.collection import CollectionMixin
from clients.gewe.video_channel import VideoChannelMixin


logger = logging.getLogger(__name__)


class GeweAPIError(Exception):
    """Base Gewe API error"""
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        response_data: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.response_data = response_data
        super().__init__(self.message)


class AsyncGeweClient(
    AccountMixin,
    MessageMixin,
    DownloadMixin,
    GroupMixin,
    ContactMixin,
    EnterpriseMixin,
    SNSMixin,
    PersonalMixin,
    TagMixin,
    CollectionMixin,
    VideoChannelMixin
):
    """Async client for interacting with Gewe WeChat API using aiohttp"""

    def __init__(self, token: str, base_url: str = "http://api.geweapi.com", timeout: int = 30):
        """
        Initialize Gewe client.

        Args:
            token: Gewe API token (X-GEWE-TOKEN)
            base_url: Base URL for Gewe API (default: http://api.geweapi.com)
            timeout: Request timeout in seconds (default: 30)
        """
        self.token = token
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=10,
                limit_per_host=5,
                ttl_dns_cache=300,
                force_close=False,
                enable_cleanup_closed=True
            )
            self._session = aiohttp.ClientSession(
                timeout=self.timeout,
                connector=connector
            )
        return self._session

    async def close(self):
        """Close aiohttp session and cleanup connections"""
        if self._session and not self._session.closed:
            try:
                await self._session.close()
            except Exception as e:
                logger.warning("Error closing Gewe client session: %s", e, exc_info=True)
            finally:
                self._session = None

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup session"""
        await self.close()

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make a non-streaming HTTP request to Gewe API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/gewe/v2/api/login/getLoginQrCode")
            json_data: JSON payload for POST requests

        Returns:
            Response JSON as dictionary

        Raises:
            GeweAPIError: If API request fails
        """
        import json as json_lib
        url = f"{self.base_url}{endpoint}"
        headers = {
            'X-GEWE-TOKEN': self.token,
            'Content-Type': 'application/json'
        }

        # Log request details
        logger.debug("🚀 [GeweAPI] Request: %s %s", method, url)
        if json_data:
            request_payload_str = json_lib.dumps(json_data, ensure_ascii=False, indent=2)
            if len(request_payload_str) > 2000:
                logger.debug(
                    "📤 [GeweAPI] Request payload (truncated):\n%s\n... (truncated, total length: %d chars)",
                    request_payload_str[:2000], len(request_payload_str)
                )
            else:
                logger.debug("📤 [GeweAPI] Request payload:\n%s", request_payload_str)
        else:
            logger.debug("📤 [GeweAPI] Request payload: (empty)")

        # Log request headers (mask token)
        headers_log = dict(headers)
        if 'X-GEWE-TOKEN' in headers_log:
            token_value = headers_log['X-GEWE-TOKEN']
            if len(token_value) > 8:
                headers_log['X-GEWE-TOKEN'] = f"{token_value[:4]}...{token_value[-4:]}"
            else:
                headers_log['X-GEWE-TOKEN'] = '*' * len(token_value)
        logger.debug("📋 [GeweAPI] Request headers: %s", headers_log)

        session = await self._get_session()

        try:
            async with session.request(method, url, headers=headers, json=json_data) as response:
                # Log response status and headers
                logger.debug(
                    "📥 [GeweAPI] Response: %s %s - Status: %d",
                    method, endpoint, response.status
                )
                logger.debug("📋 [GeweAPI] Response headers: %s", dict(response.headers))

                # Get response data
                try:
                    response_data = await response.json()
                except Exception as json_error:
                    # If JSON parsing fails, try to get text
                    response_text = await response.text()
                    logger.error(
                        "❌ [GeweAPI] Failed to parse JSON response: %s. Raw response: %s",
                        json_error, response_text[:500]
                    )
                    raise GeweAPIError(
                        f"Invalid JSON response: {str(json_error)}",
                        status_code=response.status
                    ) from json_error

                # Log full response structure
                response_str = json_lib.dumps(response_data, ensure_ascii=False, indent=2)
                if len(response_str) > 2000:
                    logger.debug(
                        "📦 [GeweAPI] Response payload (truncated):\n%s\n... (truncated, total length: %d chars)",
                        response_str[:2000], len(response_str)
                    )
                else:
                    logger.debug("📦 [GeweAPI] Response payload:\n%s", response_str)

                # Log response structure details
                logger.debug("🔍 [GeweAPI] Response structure analysis:")
                logger.debug("   - Top-level keys: %s", list(response_data.keys()))
                if 'ret' in response_data:
                    logger.debug("   - ret (return code): %s", response_data.get('ret'))
                if 'msg' in response_data:
                    logger.debug("   - msg (message): %s", response_data.get('msg'))
                if 'data' in response_data:
                    data = response_data.get('data')
                    if isinstance(data, dict):
                        logger.debug("   - data keys: %s", list(data.keys()))
                    elif isinstance(data, list):
                        logger.debug("   - data type: list (length: %d)", len(data))
                    else:
                        logger.debug("   - data type: %s", type(data).__name__)

                if response.status != 200:
                    error_msg = response_data.get('msg', f'API request failed with status {response.status}')
                    logger.error("❌ [GeweAPI] HTTP error: %s - %s", response.status, error_msg)
                    raise GeweAPIError(error_msg, status_code=response.status)

                ret_code = response_data.get('ret')
                if ret_code != 200:
                    error_msg = response_data.get('msg', f'API returned error code {ret_code}')
                    # Check if there's a more detailed error message in data.msg
                    data = response_data.get('data', {})
                    if isinstance(data, dict) and data.get('msg'):
                        detailed_msg = data.get('msg', '')
                        if detailed_msg:
                            error_msg = f"{error_msg} {detailed_msg}"
                    logger.error("❌ [GeweAPI] API error: ret=%s - %s", ret_code, error_msg)
                    raise GeweAPIError(
                        error_msg,
                        status_code=ret_code,
                        error_code=str(ret_code),
                        response_data=response_data
                    )

                logger.debug("✅ [GeweAPI] Request successful: %s %s", method, endpoint)
                return response_data

        except aiohttp.ClientError as e:
            logger.error("❌ [GeweAPI] Connection error: %s", e, exc_info=True)
            raise GeweAPIError(f"Connection error: {str(e)}") from e
        except GeweAPIError:
            # Re-raise GeweAPIError as-is
            raise
        except Exception as e:
            logger.error("❌ [GeweAPI] Unexpected error: %s", e, exc_info=True)
            raise GeweAPIError(f"Unexpected error: {str(e)}") from e
