"""Shared models for platform browser asset detection and download."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from file_reader.platform_browser.youtube_po import YouTubePoCapture
from file_reader.wechat_channels.models import CapturedChannelVideo


@dataclass(frozen=True)
class DetectedAsset:
    """One downloadable item discovered on the current page."""

    asset_id: str
    title: str
    format_label: str
    platform_id: str
    extractor: str
    selected: bool = True
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProbeContext:
    """Inputs for extractor probes."""

    page_url: str
    login_state: dict[str, Any]
    cookies: list[Any]
    smartedu_token: str
    captured_media_urls: tuple[str, ...] = ()
    youtube_po_capture: YouTubePoCapture | None = None
    captured_channels_videos: tuple[CapturedChannelVideo, ...] = ()
    channels_keystreams: tuple[tuple[str, str], ...] = ()
    download_folder: Path | None = None


@dataclass(frozen=True)
class ProbeResult:
    """Probe output plus whether download should be enabled."""

    assets: tuple[DetectedAsset, ...]
    download_enabled: bool
    badge_count: int = 0
    status_hint: str = ""


def badge_asset_count(assets: tuple[DetectedAsset, ...]) -> int:
    """Count logical items for the download badge (one per video, not per format)."""
    groups: set[str] = set()
    for asset in assets:
        group_id = asset.meta.get("group_id")
        if group_id:
            groups.add(str(group_id))
        else:
            groups.add(asset.asset_id)
    return len(groups)
