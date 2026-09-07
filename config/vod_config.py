"""Tencent Cloud VOD (云点播) configuration.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import TYPE_CHECKING, Any


class VodConfigMixin:
    """TTLs, procedure, and public TCPlayer license for 云点播."""

    if TYPE_CHECKING:

        def _get_cached_value(self, _key: str, _default: Any = None) -> Any:
            """Type stub: method provided by BaseConfig."""
            raise NotImplementedError

    @property
    def TENCENT_VOD_APP_ID(self) -> str:
        """VOD application / SubAppId (integer string)."""
        return str(self._get_cached_value("TENCENT_VOD_APP_ID", "") or "").strip()

    @property
    def TENCENT_VOD_PLAY_KEY(self) -> str:
        """Default distribution PlayKey (播放密钥), not KEY 防盗链."""
        return str(self._get_cached_value("TENCENT_VOD_PLAY_KEY", "") or "").strip()

    @property
    def TENCENT_VOD_LICENSE_URL(self) -> str:
        """Public TCPlayer license URL from the 视立方 console."""
        return str(self._get_cached_value("TENCENT_VOD_LICENSE_URL", "") or "").strip()

    @property
    def TENCENT_VOD_LICENSE_KEY(self) -> str:
        """Public TCPlayer license key from the 视立方 console."""
        return str(self._get_cached_value("TENCENT_VOD_LICENSE_KEY", "") or "").strip()

    @property
    def TENCENT_VOD_REGION(self) -> str:
        """Cloud API region for vod.tencentcloudapi.com."""
        raw = str(self._get_cached_value("TENCENT_VOD_REGION", "ap-guangzhou") or "")
        return raw.strip() or "ap-guangzhou"

    @property
    def TENCENT_VOD_PROCEDURE(self) -> str:
        """Optional task-flow name baked into client upload signatures."""
        return str(self._get_cached_value("TENCENT_VOD_PROCEDURE", "") or "").strip()

    @property
    def TENCENT_VOD_PSIGN_TTL(self) -> int:
        """Seconds until a player signature expires (default 6 hours)."""
        return int(self._get_cached_value("TENCENT_VOD_PSIGN_TTL", "21600"))

    @property
    def TENCENT_VOD_UPLOAD_TTL(self) -> int:
        """Seconds until a client upload signature expires (default 2 hours)."""
        return int(self._get_cached_value("TENCENT_VOD_UPLOAD_TTL", "7200"))

    @property
    def TENCENT_VOD_ADAPTIVE_DEFINITION(self) -> int:
        """Adaptive HLS template id used in psign contentInfo."""
        return int(self._get_cached_value("TENCENT_VOD_ADAPTIVE_DEFINITION", "10"))
