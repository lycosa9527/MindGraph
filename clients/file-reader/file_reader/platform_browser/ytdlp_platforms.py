"""yt-dlp platform host and cookie configuration."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from file_reader.platform_browser.sites import detect_platform, get_platform


@dataclass(frozen=True)
class YtdlpPlatformConfig:
    """Per-platform yt-dlp settings."""

    platform_id: str
    host_suffixes: tuple[str, ...]
    short_link_hosts: tuple[str, ...] = ()
    export_all_cookies: bool = True


_YTDLP_PLATFORMS: tuple[YtdlpPlatformConfig, ...] = (
    YtdlpPlatformConfig(
        platform_id="bilibili",
        host_suffixes=("bilibili.com", "b23.tv"),
        short_link_hosts=("b23.tv",),
    ),
    YtdlpPlatformConfig(
        platform_id="youtube",
        host_suffixes=("youtube.com", "youtu.be"),
    ),
    YtdlpPlatformConfig(
        platform_id="douyin",
        host_suffixes=("douyin.com", "iesdouyin.com"),
        short_link_hosts=("v.douyin.com",),
    ),
    YtdlpPlatformConfig(
        platform_id="tiktok",
        host_suffixes=("tiktok.com",),
        short_link_hosts=("vm.tiktok.com", "vt.tiktok.com", "tiktok.com"),
    ),
)


def ytdlp_platform_configs() -> tuple[YtdlpPlatformConfig, ...]:
    """Return all yt-dlp platform definitions."""
    return _YTDLP_PLATFORMS


def ytdlp_host_suffixes() -> tuple[str, ...]:
    """Return all host suffixes handled by yt-dlp."""
    suffixes: list[str] = []
    for row in _YTDLP_PLATFORMS:
        suffixes.extend(row.host_suffixes)
    return tuple(suffixes)


def ytdlp_platform_id_for_url(url: str) -> str:
    """Map a page URL to a yt-dlp platform id."""
    host = (urlparse(url).hostname or "").lower()
    for row in _YTDLP_PLATFORMS:
        for suffix in row.host_suffixes:
            if host == suffix or host.endswith(f".{suffix}"):
                return row.platform_id
    return "unknown"


def ytdlp_allowed(url: str) -> bool:
    """Return True when yt-dlp should handle the URL."""
    return ytdlp_platform_id_for_url(url) != "unknown"


def ytdlp_config_for_platform(platform_id: str) -> YtdlpPlatformConfig | None:
    """Return config for a platform id."""
    for row in _YTDLP_PLATFORMS:
        if row.platform_id == platform_id:
            return row
    return None


def ytdlp_short_link_host(url: str) -> str:
    """Return the host when the URL is a known short link."""
    host = (urlparse(url).hostname or "").lower()
    for row in _YTDLP_PLATFORMS:
        if host in row.short_link_hosts:
            return host
    return ""


def validate_ytdlp_site_registry() -> None:
    """Ensure yt-dlp platforms are registered in sites.py host detection."""
    for row in _YTDLP_PLATFORMS:
        site = get_platform(row.platform_id)
        if not site.ytdlp_host:
            raise ValueError(f"Platform {row.platform_id} is missing ytdlp_host in sites registry")
        for suffix in row.host_suffixes:
            if suffix == "b23.tv":
                probe_url = "https://b23.tv/abc123"
            elif suffix == "youtu.be":
                probe_url = "https://youtu.be/abc123"
            else:
                probe_url = f"https://www.{suffix}/watch/test"
            detected = detect_platform(probe_url)
            if detected.site_id != row.platform_id:
                raise ValueError(
                    f"Host suffix {suffix!r} maps to {detected.site_id!r}, expected {row.platform_id!r}",
                )
