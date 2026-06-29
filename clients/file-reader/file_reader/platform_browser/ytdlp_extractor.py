"""yt-dlp extraction for supported video hosts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse
from urllib.request import Request, urlopen

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

from file_reader.platform_browser.cookie_jar import write_netscape_cookie_file
from file_reader.platform_browser.models import DetectedAsset, ProbeContext
from file_reader.platform_browser.youtube_po import (
    YouTubePoCapture,
    is_youtube_po_error,
    is_youtube_watch_url,
)
from file_reader.platform_browser.ytdlp_options import build_ytdlp_ydl_opts
from file_reader.platform_browser.ytdlp_platforms import (
    ytdlp_allowed,
    ytdlp_config_for_platform,
    ytdlp_platform_id_for_url,
    ytdlp_short_link_host,
)
from file_reader.smartedu.debug_log import log_platform_browser


def _yt_dlp_error_types() -> tuple[type[BaseException], ...]:
    types: tuple[type[BaseException], ...] = (OSError, ValueError, KeyError)
    if yt_dlp is not None:
        return types + (yt_dlp.utils.DownloadError,)
    return types


def _cookie_header_for_url(cookies: list[Any], page_url: str) -> str:
    """Build a Cookie header for short-link resolution."""
    host = (urlparse(page_url).hostname or "").lower()
    parts: list[str] = []
    for cookie in cookies:
        name = str(getattr(cookie, "name", "") or "")
        value = str(getattr(cookie, "value", "") or "")
        domain = str(getattr(cookie, "domain", "") or "").lower().lstrip(".")
        if not name or not value or not domain:
            continue
        if host == domain or host.endswith(f".{domain}") or domain in host:
            parts.append(f"{name}={value}")
    return "; ".join(parts)


def resolve_page_url(raw_url: str, cookies: list[Any] | None = None) -> str:
    """Follow short redirects before probing."""
    text = (raw_url or "").strip()
    if not text:
        return ""
    if not text.startswith(("http://", "https://")):
        text = f"https://{text}"
    if not ytdlp_short_link_host(text):
        return text
    headers = {"User-Agent": "MindGraph-FileReader/1.0"}
    cookie_header = _cookie_header_for_url(list(cookies or []), text)
    if cookie_header:
        headers["Cookie"] = cookie_header
    request = Request(text, method="HEAD", headers=headers)
    try:
        with urlopen(request, timeout=15) as response:
            final = response.geturl()
    except OSError as exc:
        log_platform_browser(f"short link resolve failed: {exc}", level="WARN")
        return text
    return final or text


def platform_id_for_url(url: str) -> str:
    """Return the platform id for a supported yt-dlp URL."""
    return ytdlp_platform_id_for_url(url)


def _format_label(entry: dict[str, Any]) -> str:
    height = entry.get("height")
    ext = str(entry.get("ext") or "unknown")
    if height:
        return f"{height}p {ext.upper()}"
    note = str(entry.get("format_note") or entry.get("format_id") or ext)
    return note


def _info_has_video_formats(info: dict[str, Any]) -> bool:
    formats = info.get("formats") or []
    if not isinstance(formats, list):
        return False
    return any(isinstance(item, dict) and item.get("vcodec") not in (None, "none") for item in formats)


def _extract_ytdlp_info(url: str, ydl_opts: dict[str, Any]) -> dict[str, Any] | None:
    if yt_dlp is None:
        return None
    download = not ydl_opts.get("skip_download", True)
    with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
        info = ydl.extract_info(url, download=download)
    return cast(dict[str, Any] | None, info if isinstance(info, dict) else None)


def _write_probe_cookies(cookies: list[Any], platform_id: str, page_url: str) -> Path:
    config = ytdlp_config_for_platform(platform_id)
    export_all = config.export_all_cookies if config is not None else True
    host = (urlparse(page_url).hostname or "").lower()
    return write_netscape_cookie_file(
        list(cookies),
        domain_filter=host,
        export_all=export_all,
    )


def _youtube_po_attempts(capture: YouTubePoCapture | None) -> tuple[YouTubePoCapture | None, ...]:
    if capture is not None and capture.usable_for_ytdlp():
        return (capture, None)
    return (None,)


def _run_youtube_ytdlp(
    url: str,
    *,
    cookie_path: Path,
    youtube_po: YouTubePoCapture | None,
    skip_download: bool,
    outtmpl: str = "",
    format_id: str = "",
) -> dict[str, Any] | None:
    """Run yt-dlp for YouTube with PO tokens then fallback clients."""
    last_error = ""
    for attempt_po in _youtube_po_attempts(youtube_po):
        ydl_opts = build_ytdlp_ydl_opts(
            cookie_path=cookie_path,
            platform_id="youtube",
            skip_download=skip_download,
            youtube_po=attempt_po,
            outtmpl=outtmpl,
            format_id=format_id,
        )
        try:
            info = _extract_ytdlp_info(url, ydl_opts)
        except _yt_dlp_error_types() as exc:
            last_error = str(exc)
            log_platform_browser(
                f"yt-dlp {'probe' if skip_download else 'download'} failed "
                f"(youtube, po={'yes' if attempt_po else 'fallback'}): {exc}",
                level="WARN",
            )
            if attempt_po is None or not isinstance(exc, Exception) or not is_youtube_po_error(exc):
                break
            continue
        if info is None:
            last_error = "yt-dlp returned no metadata"
            continue
        if skip_download and not _info_has_video_formats(info):
            last_error = "no video formats returned"
            continue
        return info
    if not skip_download and last_error:
        raise ValueError(last_error)
    return None


def _run_ytdlp_download(
    url: str,
    *,
    cookie_path: Path,
    platform_id: str,
    outtmpl: str,
    format_id: str,
) -> dict[str, Any]:
    """Download one non-YouTube yt-dlp asset."""
    ydl_opts = build_ytdlp_ydl_opts(
        cookie_path=cookie_path,
        platform_id=platform_id,
        skip_download=False,
        outtmpl=outtmpl,
        format_id=format_id,
    )
    try:
        info = _extract_ytdlp_info(url, ydl_opts)
    except _yt_dlp_error_types() as exc:
        raise ValueError(str(exc)) from exc
    if info is None:
        raise ValueError("yt-dlp returned no file")
    return info


def _resolve_ytdlp_output_path(info: dict[str, Any], folder: Path, title_stem: str) -> Path:
    downloads = info.get("requested_downloads")
    if isinstance(downloads, list) and downloads:
        filepath = downloads[0].get("filepath")
        if filepath:
            return Path(str(filepath))
    filepath = info.get("_filename")
    if filepath:
        return Path(str(filepath))
    matches = sorted(folder.glob(f"{title_stem}.*"))
    if matches:
        return matches[-1]
    raise ValueError("yt-dlp download path unknown")


def download_ytdlp_asset(
    asset: DetectedAsset,
    folder: Path,
    context: ProbeContext,
    *,
    safe_name_fn,
) -> Path:
    """Download one yt-dlp asset using the same YouTube fallbacks as probe."""
    if yt_dlp is None:
        raise ValueError("yt-dlp not installed")
    page_url = str(asset.meta.get("page_url") or context.page_url).strip()
    if not page_url:
        page_url = resolve_page_url(context.page_url, list(context.cookies))
    format_id = str(asset.meta.get("format_id") or "")
    platform_id = platform_id_for_url(page_url)
    if platform_id == "unknown":
        raise ValueError("Unsupported yt-dlp URL")
    host = (urlparse(page_url).hostname or "").lower()
    config = ytdlp_config_for_platform(platform_id)
    export_all = config.export_all_cookies if config is not None else True
    cookie_path = write_netscape_cookie_file(
        list(context.cookies),
        domain_filter=host,
        export_all=export_all,
    )
    title_stem = safe_name_fn(asset.title)
    out_template = str(folder / f"{title_stem}.%(ext)s")
    youtube_po = context.youtube_po_capture
    if platform_id == "youtube" and not isinstance(youtube_po, YouTubePoCapture):
        youtube_po = None
    try:
        if platform_id == "youtube":
            info = _run_youtube_ytdlp(
                page_url,
                cookie_path=cookie_path,
                youtube_po=youtube_po,
                skip_download=False,
                outtmpl=out_template,
                format_id=format_id,
            )
            if info is None:
                raise ValueError("yt-dlp YouTube download failed")
        else:
            info = _run_ytdlp_download(
                page_url,
                cookie_path=cookie_path,
                platform_id=platform_id,
                outtmpl=out_template,
                format_id=format_id,
            )
    finally:
        cookie_path.unlink(missing_ok=True)
    return _resolve_ytdlp_output_path(info, folder, title_stem)


def probe_ytdlp_assets(context: ProbeContext) -> tuple[DetectedAsset, ...]:
    """List yt-dlp formats for supported video hosts."""
    url = resolve_page_url(context.page_url, list(context.cookies))
    if not url or not ytdlp_allowed(url):
        return ()
    if yt_dlp is None:
        log_platform_browser("yt-dlp not installed", level="WARN")
        return ()

    platform_id = platform_id_for_url(url)
    cookie_path = _write_probe_cookies(list(context.cookies), platform_id, url)
    try:
        if platform_id == "youtube":
            info = _run_youtube_ytdlp(
                url,
                cookie_path=cookie_path,
                youtube_po=context.youtube_po_capture,
                skip_download=True,
            )
        else:
            ydl_opts = build_ytdlp_ydl_opts(
                cookie_path=cookie_path,
                platform_id=platform_id,
                skip_download=True,
            )
            try:
                info = _extract_ytdlp_info(url, ydl_opts)
            except _yt_dlp_error_types() as exc:
                log_platform_browser(f"yt-dlp probe failed ({platform_id}): {exc}", level="WARN")
                info = None
    finally:
        cookie_path.unlink(missing_ok=True)

    if info is None:
        return ()

    entries = info.get("entries")
    if entries:
        assets: list[DetectedAsset] = []
        for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                continue
            assets.extend(_formats_from_info(entry, platform_id, part_index=index))
        return tuple(assets)

    return tuple(_formats_from_info(info, platform_id))


def ytdlp_probe_status_hint(context: ProbeContext, assets: tuple[DetectedAsset, ...]) -> str:
    """Return a UI hint when playback/login/cookies are needed."""
    if assets:
        return ""
    platform_id = platform_id_for_url(context.page_url)
    if platform_id == "youtube":
        if not is_youtube_watch_url(context.page_url):
            return ""
        capture = context.youtube_po_capture
        if capture is not None and capture.usable_for_ytdlp():
            return "youtube_po_retry"
        return "youtube_po_needed"
    if platform_id in {"douyin", "tiktok", "bilibili"}:
        return "ytdlp_cookies_needed"
    return ""


def youtube_probe_status_hint(context: ProbeContext, assets: tuple[DetectedAsset, ...]) -> str:
    """Backward-compatible alias for YouTube-only status hints."""
    hint = ytdlp_probe_status_hint(context, assets)
    if hint.startswith("youtube_"):
        return hint
    return ""


def _formats_from_info(
    info: dict[str, Any],
    platform_id: str,
    *,
    part_index: int | None = None,
) -> list[DetectedAsset]:
    title = str(info.get("title") or "video")
    if part_index is not None:
        title = f"{title} (P{part_index})"
    group_id = f"{info.get('id') or title}:{part_index or 0}"
    formats = info.get("formats") or []
    if not isinstance(formats, list):
        return []
    video_formats = [item for item in formats if isinstance(item, dict) and item.get("vcodec") not in (None, "none")]
    if not video_formats:
        return []
    best_by_ext: dict[str, dict[str, Any]] = {}
    for entry in video_formats:
        format_id = str(entry.get("format_id") or entry.get("ext") or "default")
        current = best_by_ext.get(format_id)
        height = int(entry.get("height") or 0)
        if current is None or height > int(current.get("height") or 0):
            best_by_ext[format_id] = entry
    ranked = sorted(
        best_by_ext.items(),
        key=lambda item: int(item[1].get("height") or 0),
        reverse=True,
    )
    if len(ranked) > 8:
        ranked = ranked[:8]
    page_url = str(
        info.get("webpage_url") or info.get("original_url") or info.get("url") or "",
    )
    assets: list[DetectedAsset] = []
    for format_id, entry in ranked:
        assets.append(
            DetectedAsset(
                asset_id=f"{info.get('id') or title}:{format_id}",
                title=title,
                format_label=_format_label(entry),
                platform_id=platform_id,
                extractor="ytdlp",
                selected=len(ranked) == 1,
                meta={
                    "page_url": page_url,
                    "format_id": format_id,
                    "group_id": group_id,
                    "ydl_format": entry,
                },
            ),
        )
    if assets and not any(item.selected for item in assets):
        assets[0] = DetectedAsset(
            asset_id=assets[0].asset_id,
            title=assets[0].title,
            format_label=assets[0].format_label,
            platform_id=assets[0].platform_id,
            extractor=assets[0].extractor,
            selected=True,
            meta=assets[0].meta,
        )
    return assets
