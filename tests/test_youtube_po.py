"""Tests for YouTube PO token helpers."""

from __future__ import annotations

from file_reader.platform_browser.youtube_po import (
    YouTubePoCapture,
    build_youtube_extractor_args,
    extract_gvs_token_from_url,
    extract_video_id_from_url,
    is_youtube_po_error,
    is_youtube_stream_capture_url,
    merge_youtube_po_capture,
    parse_youtube_po_probe,
)
from file_reader.platform_browser.ytdlp_options import build_ytdlp_ydl_opts


def test_extract_gvs_token_from_googlevideo_url() -> None:
    """GVS PO tokens are parsed from googlevideo stream URLs."""
    url = "https://rr5---sn-abc.googlevideo.com/videoplayback?pot=abc123&id=VIDEOID"
    assert extract_gvs_token_from_url(url) == "abc123"
    assert is_youtube_stream_capture_url(url) is True


def test_extract_video_id_from_watch_url() -> None:
    """Watch URLs expose the video id."""
    assert extract_video_id_from_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_build_youtube_extractor_args_with_capture() -> None:
    """Captured tokens map to yt-dlp mweb PO token args."""
    capture = YouTubePoCapture(gvs_token="gvs123", player_token="player456")
    args = build_youtube_extractor_args(capture)
    assert args["player_client"] == ["mweb"]
    assert "mweb.gvs+gvs123" in args["po_token"]
    assert "mweb.player+player456" in args["po_token"]


def test_build_youtube_extractor_args_fallback_clients() -> None:
    """Without PO tokens, fall back to cookie-friendly clients."""
    args = build_youtube_extractor_args(None)
    assert args["player_client"] == ["tv", "web_safari"]
    assert "po_token" not in args


def test_build_ytdlp_ydl_opts_youtube_includes_extractor_args(tmp_path) -> None:
    """YouTube yt-dlp options include extractor args."""
    cookie_path = tmp_path / "cookies.txt"
    cookie_path.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    opts = build_ytdlp_ydl_opts(
        cookie_path=cookie_path,
        platform_id="youtube",
        skip_download=True,
        youtube_po=YouTubePoCapture(gvs_token="abc"),
    )
    assert "extractor_args" in opts
    assert opts["extractor_args"]["youtube"]["player_client"] == ["mweb"]


def test_parse_youtube_po_probe_json() -> None:
    """Hook read JS JSON is parsed into capture state."""
    capture = parse_youtube_po_probe('{"player":"p1","videoId":"vid1","gvs":""}')
    assert capture is not None
    assert capture.player_token == "p1"
    assert capture.video_id == "vid1"


def test_merge_youtube_po_capture_stream_url() -> None:
    """Stream URL capture updates the GVS token."""
    merged = merge_youtube_po_capture(
        None,
        stream_url="https://rr5---sn-abc.googlevideo.com/videoplayback?pot=tok1",
    )
    assert merged is not None
    assert merged.gvs_token == "tok1"


def test_is_youtube_po_error() -> None:
    """PO token failures are recognized from yt-dlp errors."""
    assert is_youtube_po_error(RuntimeError("Some web client formats require a PO Token")) is True
    assert is_youtube_po_error(RuntimeError("network timeout")) is False
