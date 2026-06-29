"""Download Tencent Meeting recording media."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from file_reader.platform_browser.http_cookies import build_cookie_header
from file_reader.smartedu.downloader import resolve_ffmpeg_path
from file_reader.smartedu.debug_log import log_platform_browser

_REFERER = "https://meeting.tencent.com/"
_CHUNK = 1024 * 256


def download_recording(
    media_url: str,
    dest: Path,
    cookies: list[Any],
    *,
    timeout: int = 3600,
) -> Path:
    """Download a cloud recording URL to dest."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    lowered = media_url.lower()
    if ".m3u8" in lowered:
        return _download_hls(media_url, dest, cookies, timeout=timeout)
    return _download_binary(media_url, dest, cookies, timeout=timeout)


def _download_binary(
    media_url: str,
    dest: Path,
    cookies: list[Any],
    *,
    timeout: int,
) -> Path:
    headers = {
        "User-Agent": "MindGraph-FileReader/1.0",
        "Referer": _REFERER,
    }
    cookie_value = build_cookie_header(cookies, media_url)
    if cookie_value:
        headers["Cookie"] = cookie_value
    request = Request(media_url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            with dest.open("wb") as handle:
                while True:
                    chunk = response.read(_CHUNK)
                    if not chunk:
                        break
                    handle.write(chunk)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"HTTP {exc.code}: {body[:200]}") from exc
    except URLError as exc:
        raise ValueError(f"Network error: {exc.reason}") from exc
    log_platform_browser(f"Tencent Meeting saved {dest}")
    return dest


def _download_hls(
    media_url: str,
    dest: Path,
    cookies: list[Any],
    *,
    timeout: int,
) -> Path:
    ffmpeg = resolve_ffmpeg_path()
    if ffmpeg is None:
        raise ValueError("ffmpeg not found — required for m3u8 recordings")
    cookie_value = build_cookie_header(cookies, media_url)
    header_lines = [f"Referer: {_REFERER}", "User-Agent: MindGraph-FileReader/1.0"]
    if cookie_value:
        header_lines.append(f"Cookie: {cookie_value}")
    headers_arg = "\r\n".join(header_lines) + "\r\n"
    command = [
        str(ffmpeg),
        "-y",
        "-headers",
        headers_arg,
        "-i",
        media_url,
        "-c",
        "copy",
        str(dest),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("ffmpeg timed out while merging recording") from exc
    except OSError as exc:
        raise ValueError(f"ffmpeg failed to start: {exc}") from exc
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        tail = stderr[-500:] if len(stderr) > 500 else stderr
        raise ValueError(tail or "ffmpeg merge failed")
    log_platform_browser(f"Tencent Meeting HLS saved {dest}")
    return dest


def safe_output_name(title: str) -> str:
    """Return a filesystem-safe stem."""
    cleaned = "".join(ch if ch not in '<>:"/\\|?*' else "_" for ch in title.strip())
    cleaned = cleaned.strip(". ") or "tencent-meeting-recording"
    return cleaned
