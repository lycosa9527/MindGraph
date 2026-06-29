"""Platform browser package — multi-site embedded browser helpers."""

from file_reader.platform_browser.models import DetectedAsset, ProbeContext, ProbeResult
from file_reader.platform_browser.registry import probe_assets, probe_assets_for_url
from file_reader.platform_browser.sites import detect_platform, format_status_line

__all__ = [
    "DetectedAsset",
    "ProbeContext",
    "ProbeResult",
    "detect_platform",
    "format_status_line",
    "probe_assets",
    "probe_assets_for_url",
]
