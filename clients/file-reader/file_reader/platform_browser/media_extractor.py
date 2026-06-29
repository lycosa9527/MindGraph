"""Media URL probe for Tencent Meeting recordings."""

from __future__ import annotations

from file_reader.platform_browser.models import DetectedAsset, ProbeContext
from file_reader.tencent_meeting.downloader import safe_output_name
from file_reader.tencent_meeting.url_parser import is_recording_page, parse_media_urls


def probe_media_assets(context: ProbeContext) -> tuple[DetectedAsset, ...]:
    """Detect direct recording media URLs on Tencent Meeting pages."""
    if not is_recording_page(context.page_url):
        return ()
    urls = parse_media_urls(None, captured=context.captured_media_urls)
    assets: list[DetectedAsset] = []
    for index, media_url in enumerate(urls, start=1):
        suffix = ".mp4" if ".mp4" in media_url.lower() else ".m3u8"
        title = safe_output_name(f"recording-{index}")
        assets.append(
            DetectedAsset(
                asset_id=f"tencent-meeting:{index}",
                title=title,
                format_label=suffix.lstrip(".").upper(),
                platform_id="tencent_meeting",
                extractor="media",
                selected=len(urls) == 1,
                meta={"media_url": media_url, "group_id": f"tencent-meeting:{index}"},
            ),
        )
    return tuple(assets)
