"""Download and optionally decrypt WeChat Channels videos."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from file_reader.platform_browser.http_cookies import build_cookie_header
from file_reader.smartedu.debug_log import log_platform_browser
from file_reader.wechat_channels.decrypt import (
    CHANNELS_ENCRYPTED_HEADER_SIZE,
    decrypt_channels_header,
    hex_to_keystream,
)
from file_reader.wechat_channels.models import CapturedChannelVideo

_REFERER = "https://channels.weixin.qq.com/"
_CHUNK = 1024 * 256


def _cookie_header(cookies: list[Any], media_url: str) -> str:
    return build_cookie_header(cookies, media_url)


def _write_response_body(
    response: Any,
    dest: Path,
    *,
    keystream: bytes,
) -> None:
    """Stream a Channels response to disk, decrypting the leading encrypted block."""
    with dest.open("wb") as handle:
        head = response.read(CHANNELS_ENCRYPTED_HEADER_SIZE)
        if not head:
            raise ValueError("Channels video response was empty")
        if keystream:
            decrypted_head = decrypt_channels_header(head, keystream)
            if b"ftyp" not in decrypted_head[:32]:
                raise ValueError("Channels decrypt failed — replay the video in the browser and retry")
            handle.write(decrypted_head)
        else:
            if b"ftyp" not in head[:32]:
                raise ValueError("Channels video is encrypted — open/play it in the embedded browser first")
            handle.write(head)
        while True:
            chunk = response.read(_CHUNK)
            if not chunk:
                break
            handle.write(chunk)


def download_channels_video(
    video: CapturedChannelVideo,
    dest: Path,
    cookies: list[Any],
    *,
    keystream_hex: str = "",
    timeout: int = 3600,
) -> Path:
    """Download and optionally decrypt one Channels video."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": "MindGraph-FileReader/1.0",
        "Referer": _REFERER,
    }
    cookie_value = _cookie_header(cookies, video.media_url)
    if cookie_value:
        headers["Cookie"] = cookie_value
    request = Request(video.media_url, headers=headers, method="GET")
    needs_decrypt = bool(video.decode_key.strip())
    keystream = b""
    if needs_decrypt:
        try:
            keystream = hex_to_keystream(keystream_hex)
        except ValueError as exc:
            raise ValueError("Invalid Channels decrypt keystream") from exc
        if not keystream:
            raise ValueError("Channels video is encrypted — open/play it in the embedded browser first")
    try:
        with urlopen(request, timeout=timeout) as response:
            _write_response_body(response, dest, keystream=keystream)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"HTTP {exc.code}: {body[:200]}") from exc
    except URLError as exc:
        raise ValueError(f"Network error: {exc.reason}") from exc

    log_platform_browser(f"WeChat Channels saved {dest}")
    return dest


def safe_output_name(title: str) -> str:
    """Return a filesystem-safe stem."""
    cleaned = "".join(ch if ch not in '<>:"/\\|?*' else "_" for ch in title.strip())
    cleaned = cleaned.strip(". ") or "wechat-channels-video"
    return cleaned
