"""Tests for platform browser shared models."""

from __future__ import annotations

from file_reader.platform_browser.models import DetectedAsset, badge_asset_count


def test_badge_asset_count_groups_ytdlp_formats() -> None:
    """Badge count collapses multiple formats for one video."""
    assets = (
        DetectedAsset(
            asset_id="v:720",
            title="Demo",
            format_label="720p MP4",
            platform_id="bilibili",
            extractor="ytdlp",
            meta={"group_id": "bv1:0"},
        ),
        DetectedAsset(
            asset_id="v:1080",
            title="Demo",
            format_label="1080p MP4",
            platform_id="bilibili",
            extractor="ytdlp",
            meta={"group_id": "bv1:0"},
        ),
        DetectedAsset(
            asset_id="lesson:pdf",
            title="Plan",
            format_label="PDF",
            platform_id="smartedu",
            extractor="smartedu",
        ),
    )
    assert badge_asset_count(assets) == 2
