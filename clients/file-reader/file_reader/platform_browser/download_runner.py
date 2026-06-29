"""Download detected assets for all supported platforms."""

from __future__ import annotations

from pathlib import Path
from threading import Event

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

from file_reader.platform_browser.download_prefs import resolve_download_dir
from file_reader.platform_browser.models import DetectedAsset, ProbeContext
from file_reader.platform_browser.sites import detect_platform
from file_reader.platform_browser.ytdlp_extractor import download_ytdlp_asset
from file_reader.smartedu.debug_log import log_platform_browser
from file_reader.smartedu.downloader import download_asset
from file_reader.smartedu.models import SmartEduAsset
from file_reader.tencent_meeting.downloader import download_recording, safe_output_name as tencent_safe_name
from file_reader.wechat_channels.downloader import download_channels_video, safe_output_name as channels_safe_name
from file_reader.wechat_channels.models import CapturedChannelVideo


def _download_error_types() -> tuple[type[BaseException], ...]:
    types: tuple[type[BaseException], ...] = (ValueError, OSError)
    if yt_dlp is not None:
        return types + (yt_dlp.utils.DownloadError,)
    return types


def _media_file_extension(media_url: str) -> str:
    lower = media_url.lower()
    if ".m3u8" in lower:
        return ".m3u8"
    return ".mp4"


def _rollback_saved(saved: list[Path]) -> None:
    for path in list(saved):
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            log_platform_browser(f"rollback unlink failed {path}: {exc}", level="WARN")
    saved.clear()


def download_detected_assets(
    assets: list[DetectedAsset],
    context: ProbeContext,
    *,
    cancel_event: Event | None = None,
) -> tuple[list[Path], list[str]]:
    """Download selected assets; return saved paths and error messages."""
    site = detect_platform(context.page_url)
    folder = context.download_folder or resolve_download_dir(site)
    saved: list[Path] = []
    errors: list[str] = []
    for asset in assets:
        if cancel_event is not None and cancel_event.is_set():
            _rollback_saved(saved)
            errors.append("Download cancelled")
            break
        try:
            path = _download_one(asset, folder, context)
            saved.append(path)
        except _download_error_types() as exc:
            errors.append(f"{asset.title}: {exc}")
            log_platform_browser(f"download failed {asset.asset_id}: {exc}", level="WARN")
    return saved, errors


def _download_one(asset: DetectedAsset, folder: Path, context: ProbeContext) -> Path:
    if asset.extractor == "smartedu":
        raw = asset.meta.get("smartedu_asset")
        if not isinstance(raw, SmartEduAsset):
            raise ValueError("Missing SmartEdu asset metadata")
        lesson_title = str(asset.meta.get("lesson_title") or asset.title)
        token = context.smartedu_token.strip()
        if not token:
            raise ValueError("SmartEdu token required")
        return download_asset(raw, folder, lesson_title, token)

    if asset.extractor == "media":
        media_url = str(asset.meta.get("media_url") or "")
        if not media_url:
            raise ValueError("Missing media URL")
        ext = _media_file_extension(media_url)
        dest = folder / f"{tencent_safe_name(asset.title)}{ext}"
        return download_recording(media_url, dest, list(context.cookies))

    if asset.extractor == "channels":
        raw = asset.meta.get("channels_video")
        if not isinstance(raw, CapturedChannelVideo):
            raise ValueError("Missing WeChat Channels metadata")
        if not raw.decode_key.strip():
            raise ValueError("Channels video metadata incomplete — play the video in the browser first")
        keystream_hex = _channels_keystream(context, raw.asset_id())
        dest = folder / f"{channels_safe_name(asset.title)}.mp4"
        return download_channels_video(
            raw,
            dest,
            list(context.cookies),
            keystream_hex=keystream_hex,
        )

    if asset.extractor == "ytdlp":
        return download_ytdlp_asset(
            asset,
            folder,
            context,
            safe_name_fn=tencent_safe_name,
        )

    raise ValueError(f"Unsupported extractor: {asset.extractor}")


def _channels_keystream(context: ProbeContext, asset_id: str) -> str:
    for key, value in context.channels_keystreams:
        if key == asset_id:
            return value
    return ""
