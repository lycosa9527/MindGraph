"""CSP hosts for browser upload and TCPlayer playback.

vod-js-sdk-v6 posts to vod2.qcloud.com, then PUTs the file to
``{bucket}.cos.{region}.myqcloud.com``. A ``*.myqcloud.com`` source does not
match that host: CSP ``*`` covers a single label only.

TCPlayer 5.3 then loads ``tcsdk.com`` scripts and calls getplayinfo on the
playvideo hosts baked into the bundle. The file itself is served from
``{appId}.vod2.myqcloud.com``.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from urllib.parse import urlparse

VOD_UPLOAD_API_ORIGINS = (
    "https://vod2.qcloud.com",
    "https://vod2.dnsv1.com",
)

# Mainland parks PrepareUploadUGC may assign. The bucket name is chosen at
# upload time, so the source is one label wide on the region host.
VOD_UPLOAD_COS_REGIONS = (
    "ap-shanghai",
    "ap-chongqing",
    "ap-guangzhou",
    "ap-beijing",
    "ap-chengdu",
    "ap-nanjing",
)


# Hosts hardcoded in tcplayer.js 5.3.4 (play CGI, license, escape-domain lookup).
VOD_PLAY_CONNECT_ORIGINS = (
    "https://playvideo.vodplayvideo.net",
    "https://playvideo.vodglcdn.com",
    "https://playvideo.vodplayvideo.com",
    "https://playvideo.vod-common.com",
    "https://license.vodplayvideo.net",
    "https://license.vodglcdn.com",
    "https://license.vodplayvideo.com",
    "https://license.vod-common.com",
    "https://get-domains.vod-backup.net",
    "https://*.vod2.myqcloud.com",
)

# TCPlayer loads hls/flv/crypto from this host at runtime. The package copy is not used.
VOD_PLAYER_SCRIPT_ORIGINS = ("https://tcsdk.com",)

# Default distribution domain is one label: ``{appId}.vod2.myqcloud.com``.
VOD_PLAY_MEDIA_ORIGINS = ("https://*.vod2.myqcloud.com",)


def license_connect_origin(license_url: str) -> str:
    """https origin of the configured TCPlayer license, or empty when it is not a host."""
    parsed = urlparse(license_url.strip())
    host = parsed.hostname or ""
    if parsed.scheme != "https" or not host:
        return ""
    if any(char in host for char in ("*", " ", "/", "\\")):
        return ""
    return f"https://{host}"


def vod_browser_connect_sources(license_url: str = "") -> str:
    """Space-separated connect-src origins for upload and playback."""
    origins: list[str] = list(VOD_UPLOAD_API_ORIGINS)
    for region in VOD_UPLOAD_COS_REGIONS:
        origins.append(f"https://*.cos.{region}.myqcloud.com")
        origins.append(f"https://*.cos.{region}.tencentcos.cn")
    origins.extend(VOD_PLAY_CONNECT_ORIGINS)
    license_origin = license_connect_origin(license_url)
    if license_origin and license_origin not in origins:
        origins.append(license_origin)
    return " ".join(origins)


def vod_browser_script_sources() -> str:
    """Space-separated script-src origins TCPlayer fetches while starting."""
    return " ".join(VOD_PLAYER_SCRIPT_ORIGINS)


def vod_browser_media_sources() -> str:
    """Space-separated media-src origins for the default VOD play domain."""
    return " ".join(VOD_PLAY_MEDIA_ORIGINS)
