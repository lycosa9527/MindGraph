"""Shared yt-dlp option builders for platform browser downloads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from file_reader.platform_browser.youtube_po import YouTubePoCapture, build_youtube_extractor_args


def build_ytdlp_ydl_opts(
    *,
    cookie_path: Path,
    platform_id: str,
    skip_download: bool,
    youtube_po: YouTubePoCapture | None = None,
    outtmpl: str = "",
    format_id: str = "",
) -> dict[str, Any]:
    """Return yt-dlp options for probe or download."""
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "cookiefile": str(cookie_path),
    }
    if skip_download:
        opts["skip_download"] = True
        opts["noplaylist"] = False
    if outtmpl:
        opts["outtmpl"] = outtmpl
        opts["merge_output_format"] = "mp4"
    if format_id:
        opts["format"] = format_id
    if platform_id == "youtube":
        opts["extractor_args"] = {"youtube": build_youtube_extractor_args(youtube_po)}
    return opts
