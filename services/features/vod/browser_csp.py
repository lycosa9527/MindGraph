"""CSP connect-src hosts for browser uploads to Tencent VOD.

vod-js-sdk-v6 posts to vod2.qcloud.com, then PUTs the file to
``{bucket}.cos.{region}.myqcloud.com``. A ``*.myqcloud.com`` source does not
match that host: CSP ``*`` covers a single label only.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

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


def vod_browser_connect_sources() -> str:
    """Space-separated connect-src origins for the VOD web upload SDK."""
    origins: list[str] = list(VOD_UPLOAD_API_ORIGINS)
    for region in VOD_UPLOAD_COS_REGIONS:
        origins.append(f"https://*.cos.{region}.myqcloud.com")
        origins.append(f"https://*.cos.{region}.tencentcos.cn")
    return " ".join(origins)
