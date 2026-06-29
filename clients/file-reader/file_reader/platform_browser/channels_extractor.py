"""WeChat Channels asset probe."""

from __future__ import annotations

from file_reader.platform_browser.models import DetectedAsset, ProbeContext
from file_reader.wechat_channels.downloader import safe_output_name
from file_reader.wechat_channels.url_parser import is_channels_page


def probe_channels_assets(context: ProbeContext) -> tuple[DetectedAsset, ...]:
    """Detect captured Channels videos on the current page."""
    if not is_channels_page(context.page_url):
        return ()
    assets: list[DetectedAsset] = []
    for index, video in enumerate(context.captured_channels_videos, start=1):
        if not video.decode_key.strip():
            continue
        title = safe_output_name(video.title or f"channels-{index}")
        assets.append(
            DetectedAsset(
                asset_id=video.asset_id(),
                title=title,
                format_label="MP4",
                platform_id="wechat_channels",
                extractor="channels",
                selected=len(context.captured_channels_videos) == 1,
                meta={
                    "channels_video": video,
                    "group_id": video.asset_id(),
                },
            ),
        )
    return tuple(assets)
