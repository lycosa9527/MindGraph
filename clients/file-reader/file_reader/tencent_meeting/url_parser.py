"""Tencent Meeting cloud recording URL helpers."""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse

_MEETING_HOST = "meeting.tencent.com"
_MEDIA_URL_RE = re.compile(
    r"https?://[^\s\"'<>]+\.(?:myqcloud\.com|qq\.com)[^\s\"'<>]*\.(?:mp4|m3u8)(?:\?[^\s\"'<>]*)?",
    re.IGNORECASE,
)


def is_recording_page(raw_url: str) -> bool:
    """Return True when the URL is a Tencent Meeting web page."""
    text = (raw_url or "").strip()
    if not text.startswith(("http://", "https://")):
        text = f"https://{text}"
    host = (urlparse(text).hostname or "").lower()
    return host == _MEETING_HOST or host.endswith(f".{_MEETING_HOST}")


def is_tencent_media_url(raw_url: str) -> bool:
    """Return True when a network URL looks like a Tencent cloud recording asset."""
    text = (raw_url or "").strip()
    if not text:
        return False
    return bool(_MEDIA_URL_RE.search(text))


MEDIA_PROBE_JS = """
(function() {
  var urls = [];
  function add(url) {
    if (!url || typeof url !== 'string') return;
    if (urls.indexOf(url) !== -1) return;
    urls.push(url);
  }
  var videos = document.querySelectorAll('video, source');
  for (var i = 0; i < videos.length; i++) {
    add(videos[i].currentSrc || videos[i].src || '');
  }
  var html = document.documentElement ? document.documentElement.innerHTML : '';
  var re = /https?:\\/\\/[^\\s"'<>]+\\.(?:myqcloud\\.com|qq\\.com)[^\\s"'<>]*\\.(?:mp4|m3u8)(?:\\?[^\\s"'<>]*)?/gi;
  var match;
  while ((match = re.exec(html)) !== null) {
    add(match[0]);
  }
  return JSON.stringify(urls);
})()
"""


def parse_media_urls(raw: object, *, captured: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Parse probe JS output and merge captured resource URLs."""
    found: list[str] = []
    seen: set[str] = set()

    def append(url: str) -> None:
        cleaned = url.strip()
        if not cleaned or cleaned in seen:
            return
        seen.add(cleaned)
        found.append(cleaned)

    for item in captured:
        append(item)

    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                append(item)
    elif isinstance(raw, str) and raw.strip():
        text = raw.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = []
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, str):
                        append(item)
        else:
            for match in _MEDIA_URL_RE.finditer(text):
                append(match.group(0))
    return tuple(found)
