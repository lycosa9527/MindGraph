"""Host-based platform detection and status formatting."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from file_reader.i18n import I18n


@dataclass(frozen=True)
class PlatformSite:
    """One browsable platform recognized from the current URL."""

    site_id: str
    name_key: str
    download_folder_name: str
    supports_download: bool
    ytdlp_host: bool = False
    media_probe: bool = False
    channels_probe: bool = False


_PLATFORM_ROWS: tuple[PlatformSite, ...] = (
    PlatformSite(
        site_id="smartedu",
        name_key="smartedu.platform.smartedu",
        download_folder_name="国家智慧教育平台",
        supports_download=True,
    ),
    PlatformSite(
        site_id="bilibili",
        name_key="smartedu.platform.bilibili",
        download_folder_name="哔哩哔哩",
        supports_download=True,
        ytdlp_host=True,
    ),
    PlatformSite(
        site_id="youtube",
        name_key="smartedu.platform.youtube",
        download_folder_name="YouTube",
        supports_download=True,
        ytdlp_host=True,
    ),
    PlatformSite(
        site_id="tiktok",
        name_key="smartedu.platform.tiktok",
        download_folder_name="TikTok",
        supports_download=True,
        ytdlp_host=True,
    ),
    PlatformSite(
        site_id="douyin",
        name_key="smartedu.platform.douyin",
        download_folder_name="抖音",
        supports_download=True,
        ytdlp_host=True,
    ),
    PlatformSite(
        site_id="wechat_channels",
        name_key="smartedu.platform.wechat_channels",
        download_folder_name="微信视频号",
        supports_download=True,
        channels_probe=True,
    ),
    PlatformSite(
        site_id="tencent_meeting",
        name_key="smartedu.platform.tencent_meeting",
        download_folder_name="腾讯会议",
        supports_download=True,
        media_probe=True,
    ),
    PlatformSite(
        site_id="baidu",
        name_key="smartedu.platform.baidu",
        download_folder_name="百度",
        supports_download=False,
    ),
    PlatformSite(
        site_id="doc360",
        name_key="smartedu.platform.doc360",
        download_folder_name="360文档",
        supports_download=False,
    ),
)

_HOST_SUFFIX_TO_ID: tuple[tuple[str, str], ...] = (
    ("smartedu.cn", "smartedu"),
    ("ykt.cbern.com.cn", "smartedu"),
    ("bilibili.com", "bilibili"),
    ("b23.tv", "bilibili"),
    ("douyin.com", "douyin"),
    ("iesdouyin.com", "douyin"),
    ("tiktok.com", "tiktok"),
    ("channels.weixin.qq.com", "wechat_channels"),
    ("youtube.com", "youtube"),
    ("youtu.be", "youtube"),
    ("meeting.tencent.com", "tencent_meeting"),
    ("baidu.com", "baidu"),
    ("360doc.com", "doc360"),
)


def detect_platform(raw_url: str) -> PlatformSite:
    """Return the platform for a page URL, or an unknown placeholder."""
    text = (raw_url or "").strip()
    if not text:
        return PlatformSite(
            site_id="unknown",
            name_key="smartedu.platform.unknown",
            download_folder_name="MindGraph",
            supports_download=False,
        )
    if not text.startswith(("http://", "https://")):
        text = f"https://{text}"
    host = (urlparse(text).hostname or "").lower()
    for suffix, site_id in _HOST_SUFFIX_TO_ID:
        if host == suffix or host.endswith(f".{suffix}"):
            return get_platform(site_id)
    return PlatformSite(
        site_id="unknown",
        name_key="smartedu.platform.unknown",
        download_folder_name=host or "MindGraph",
        supports_download=False,
    )


def get_platform(site_id: str) -> PlatformSite:
    """Return a known platform definition by id."""
    for row in _PLATFORM_ROWS:
        if row.site_id == site_id:
            return row
    return PlatformSite(
        site_id="unknown",
        name_key="smartedu.platform.unknown",
        download_folder_name="MindGraph",
        supports_download=False,
    )


def default_download_dir(site: PlatformSite) -> Path:
    """Return the default download folder for a platform."""
    path = Path.home() / "Downloads" / site.download_folder_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def platform_logged_in(
    site: PlatformSite,
    login_state: dict[str, Any],
    *,
    smartedu_token: str = "",
) -> bool:
    """Return True when login signals indicate an authenticated session."""
    if site.site_id == "smartedu":
        if login_state.get("smartedu_logged_in"):
            return True
        return bool(smartedu_token.strip())
    if site.site_id == "bilibili":
        return bool(login_state.get("bilibili_logged_in"))
    if site.site_id == "youtube":
        return bool(login_state.get("youtube_logged_in"))
    if site.site_id == "douyin":
        return bool(login_state.get("douyin_logged_in"))
    if site.site_id == "tiktok":
        return bool(login_state.get("tiktok_logged_in"))
    if site.site_id == "wechat_channels":
        return bool(login_state.get("wechat_channels_logged_in"))
    if site.site_id == "tencent_meeting":
        return bool(login_state.get("tencent_meeting_logged_in"))
    if site.site_id == "baidu":
        return bool(login_state.get("baidu_logged_in"))
    if site.site_id == "doc360":
        return bool(login_state.get("doc360_logged_in"))
    return False


def download_auth_ready(
    site: PlatformSite,
    login_state: dict[str, Any],
    *,
    smartedu_token: str,
    asset_count: int,
) -> bool:
    """Return True when download is allowed for the current platform."""
    if asset_count <= 0 or not site.supports_download:
        return False
    if site.site_id == "smartedu":
        return bool(smartedu_token.strip())
    if site.site_id == "bilibili":
        return True
    if site.site_id == "youtube":
        return True
    if site.site_id == "douyin":
        return True
    if site.site_id == "tiktok":
        return True
    if site.site_id == "wechat_channels":
        return asset_count > 0
    if site.site_id == "tencent_meeting":
        return platform_logged_in(site, login_state) and asset_count > 0
    return False


def format_status_line(
    i18n: I18n,
    site: PlatformSite,
    login_state: dict[str, Any],
    *,
    smartedu_token: str,
    page_url: str,
    status_hint: str = "",
    download_ready: bool = False,
) -> str:
    """Build the single-line platform status label."""
    if site.site_id == "unknown":
        host = (urlparse(page_url).hostname or "").strip()
        name = host or i18n.translate("smartedu.platform.unknown")
    else:
        name = i18n.translate(site.name_key)
    if download_ready:
        state = i18n.translate("smartedu.platform.download_ready")
    else:
        logged_in = platform_logged_in(site, login_state, smartedu_token=smartedu_token)
        state_key = "smartedu.platform.logged_in" if logged_in else "smartedu.platform.not_logged_in"
        state = i18n.translate(state_key)
        if site.site_id == "smartedu" and smartedu_token.strip():
            state = f"{state} · {i18n.translate('smartedu.platform.token_saved')}"
        if site.site_id == "youtube" and status_hint == "youtube_po_needed":
            state = i18n.translate("smartedu.platform.youtube_po_needed")
        elif site.site_id == "youtube" and status_hint == "youtube_po_ready":
            state = f"{state} · {i18n.translate('smartedu.platform.youtube_po_ready')}"
        elif site.site_id == "youtube" and status_hint == "youtube_po_retry":
            state = f"{state} · {i18n.translate('smartedu.platform.youtube_po_retry')}"
        elif site.site_id == "bilibili" and status_hint == "ytdlp_cookies_needed":
            state = i18n.translate("smartedu.platform.bilibili_cookies_needed")
        elif site.site_id == "douyin" and status_hint == "ytdlp_cookies_needed":
            state = i18n.translate("smartedu.platform.douyin_cookies_needed")
        elif site.site_id == "tiktok" and status_hint == "ytdlp_cookies_needed":
            state = i18n.translate("smartedu.platform.tiktok_cookies_needed")
        elif site.site_id == "wechat_channels" and status_hint == "channels_play_needed":
            state = i18n.translate("smartedu.platform.channels_play_needed")
        elif status_hint == "resource_capture_disabled":
            state = i18n.translate("smartedu.platform.resource_capture_disabled")
        elif site.site_id == "smartedu" and status_hint == "smartedu_token_required":
            state = i18n.translate("smartedu.platform.smartedu_token_required")
        elif site.site_id == "smartedu" and status_hint == "smartedu_lesson_required":
            state = i18n.translate("smartedu.platform.smartedu_lesson_required")
        elif site.site_id == "smartedu" and status_hint == "smartedu_lesson_not_found":
            state = i18n.translate("smartedu.platform.smartedu_lesson_not_found")
    return f"{name}：{state}"
