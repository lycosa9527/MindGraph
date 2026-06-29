"""Route page URLs to platform-specific asset probes."""

from __future__ import annotations

from pathlib import Path

from file_reader.platform_browser.channels_extractor import probe_channels_assets
from file_reader.platform_browser.media_extractor import probe_media_assets
from file_reader.platform_browser.models import DetectedAsset, ProbeContext, ProbeResult, badge_asset_count
from file_reader.platform_browser.sites import (
    detect_platform,
    download_auth_ready,
)
from file_reader.platform_browser.smartedu_extractor import (
    probe_smartedu_assets,
    smartedu_probe_status_hint,
)
from file_reader.platform_browser.youtube_po import YouTubePoCapture
from file_reader.platform_browser.ytdlp_extractor import (
    probe_ytdlp_assets,
    ytdlp_probe_status_hint,
)
from file_reader.wechat_channels.models import CapturedChannelVideo
from file_reader.wechat_channels.url_parser import is_channels_page
from file_reader.smartedu.debug_log import log_platform_browser, redact_url_for_log


def probe_assets(context: ProbeContext) -> ProbeResult:
    """Probe downloadable assets for the current page."""
    site = detect_platform(context.page_url)
    assets: list[DetectedAsset] = []
    if site.site_id == "smartedu":
        assets.extend(probe_smartedu_assets(context))
    elif site.ytdlp_host:
        assets.extend(probe_ytdlp_assets(context))
    elif site.channels_probe:
        assets.extend(probe_channels_assets(context))
    elif site.media_probe:
        assets.extend(probe_media_assets(context))
    count = len(assets)
    enabled = download_auth_ready(
        site,
        context.login_state,
        smartedu_token=context.smartedu_token,
        asset_count=count,
    )
    badge_count = badge_asset_count(tuple(assets))
    status_hint = ""
    if site.site_id == "smartedu":
        status_hint = smartedu_probe_status_hint(context, tuple(assets))
    elif site.ytdlp_host:
        status_hint = ytdlp_probe_status_hint(context, tuple(assets))
    elif site.channels_probe and is_channels_page(context.page_url) and not assets:
        status_hint = "channels_play_needed"
    log_platform_browser(
        f"probe site={site.site_id} url={redact_url_for_log(context.page_url)} assets={count} "
        f"badge={badge_count} enabled={enabled} hint={status_hint or '-'}",
    )
    return ProbeResult(
        assets=tuple(assets),
        download_enabled=enabled,
        badge_count=badge_count,
        status_hint=status_hint,
    )


def probe_assets_for_url(
    page_url: str,
    login_state: dict,
    cookies: list,
    *,
    smartedu_token: str,
    captured_media_urls: tuple[str, ...] = (),
    youtube_po_capture: YouTubePoCapture | None = None,
    captured_channels_videos: tuple[CapturedChannelVideo, ...] = (),
    channels_keystreams: tuple[tuple[str, str], ...] = (),
    download_folder: Path | None = None,
) -> ProbeResult:
    """Convenience wrapper building ProbeContext."""
    context = ProbeContext(
        page_url=page_url,
        login_state=login_state,
        cookies=cookies,
        smartedu_token=smartedu_token,
        captured_media_urls=captured_media_urls,
        youtube_po_capture=youtube_po_capture,
        captured_channels_videos=captured_channels_videos,
        channels_keystreams=channels_keystreams,
        download_folder=download_folder,
    )
    return probe_assets(context)
