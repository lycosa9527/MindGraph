"""YouTube Proof-of-Origin token capture and yt-dlp wiring."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

from file_reader.smartedu.debug_log import log_platform_browser

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,}$")

YOUTUBE_PO_HOOK_JS = """
(function() {
  if (window.__mgPotHookInstalled) return 'ok';
  window.__mgPotHookInstalled = true;
  window.__mgYoutubePo = window.__mgYoutubePo || { player: '', videoId: '', gvs: '' };
  function notePo(bodyText) {
    if (!bodyText) return;
    var poMatch = bodyText.match(/"poToken"\\s*:\\s*"([^"\\\\]+)"/);
    if (poMatch) window.__mgYoutubePo.player = poMatch[1];
    var vidMatch = bodyText.match(/"videoId"\\s*:\\s*"([^"\\\\]+)"/);
    if (vidMatch) window.__mgYoutubePo.videoId = vidMatch[1];
  }
  var origFetch = window.fetch;
  if (origFetch) {
    window.fetch = function(input, init) {
      try {
        var url = (typeof input === 'string') ? input : (input && input.url) || '';
        if (url.indexOf('/youtubei/v1/player') !== -1 && init && init.body) {
          notePo(typeof init.body === 'string' ? init.body : '');
        }
      } catch (e) {}
      return origFetch.apply(this, arguments);
    };
  }
  var origOpen = XMLHttpRequest.prototype.open;
  var origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url) {
    this.__mgUrl = url || '';
    return origOpen.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function(body) {
    try {
      if ((this.__mgUrl || '').indexOf('/youtubei/v1/player') !== -1) {
        notePo(typeof body === 'string' ? body : '');
      }
    } catch (e) {}
    return origSend.apply(this, arguments);
  };
  return 'ok';
})()
"""

YOUTUBE_PO_READ_JS = """
(function() {
  var po = window.__mgYoutubePo || {};
  var vid = po.videoId || '';
  if (!vid) {
    var m = location.href.match(/[?&]v=([^&]+)/);
    if (m) vid = m[1];
    else {
      var m2 = location.pathname.match(/\\/shorts\\/([^/?]+)/);
      if (m2) vid = m2[1];
    }
  }
  return JSON.stringify({ player: po.player || '', videoId: vid || '', gvs: po.gvs || '' });
})()
"""

YOUTUBE_PO_CLEANUP_JS = """
(function() {
  try {
    delete window.__mgPotHookInstalled;
    delete window.__mgYoutubePo;
  } catch (e) {}
  return 'ok';
})()
"""


@dataclass(frozen=True)
class YouTubePoCapture:
    """PO tokens captured from the embedded YouTube session."""

    gvs_token: str = ""
    player_token: str = ""
    video_id: str = ""

    def usable_for_ytdlp(self) -> bool:
        """Return True when at least one PO token is available."""
        return bool(self.gvs_token.strip() or self.player_token.strip())


def is_youtube_watch_url(raw_url: str) -> bool:
    """Return True for YouTube watch, embed, or shorts URLs."""
    text = (raw_url or "").strip()
    if not text.startswith(("http://", "https://")):
        text = f"https://{text}"
    host = (urlparse(text).hostname or "").lower()
    if "youtube.com" not in host and host not in {"youtu.be", "www.youtu.be"}:
        return False
    path = urlparse(text).path or ""
    if host.endswith("youtu.be"):
        return bool(path.strip("/"))
    return "/watch" in path or "/shorts/" in path or "/embed/" in path or "/live/" in path


def extract_video_id_from_url(raw_url: str) -> str:
    """Parse a YouTube video id from a page URL."""
    text = (raw_url or "").strip()
    if not text.startswith(("http://", "https://")):
        text = f"https://{text}"
    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    if host.endswith("youtu.be"):
        candidate = parsed.path.strip("/").split("/")[0]
        return candidate if _VIDEO_ID_RE.match(candidate) else ""
    query = parse_qs(parsed.query)
    video_ids = query.get("v") or []
    if video_ids and _VIDEO_ID_RE.match(video_ids[0]):
        return video_ids[0]
    for pattern in (r"^/shorts/([^/?]+)", r"^/embed/([^/?]+)", r"^/live/([^/?]+)"):
        match = re.search(pattern, parsed.path or "")
        if match and _VIDEO_ID_RE.match(match.group(1)):
            return match.group(1)
    return ""


def extract_gvs_token_from_url(raw_url: str) -> str:
    """Return the session GVS PO token from a googlevideo stream URL."""
    query = parse_qs(urlparse(raw_url).query)
    values = query.get("pot") or []
    token = str(values[0] or "").strip() if values else ""
    return token


def is_youtube_stream_capture_url(raw_url: str) -> bool:
    """Return True when a network URL may carry a YouTube GVS PO token."""
    host = (urlparse(raw_url).hostname or "").lower()
    if "googlevideo.com" not in host:
        return False
    return bool(extract_gvs_token_from_url(raw_url))


def parse_youtube_po_probe(raw: Any) -> YouTubePoCapture | None:
    """Parse YOUTUBE_PO_READ_JS output."""
    payload: dict[str, Any] = {}
    if isinstance(raw, dict):
        payload = raw
    elif isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {}
        payload = parsed if isinstance(parsed, dict) else {}
    gvs_token = str(payload.get("gvs") or "").strip()
    player_token = str(payload.get("player") or "").strip()
    video_id = str(payload.get("videoId") or "").strip()
    if not gvs_token and not player_token and not video_id:
        return None
    return YouTubePoCapture(
        gvs_token=gvs_token,
        player_token=player_token,
        video_id=video_id,
    )


def merge_youtube_po_capture(
    current: YouTubePoCapture | None,
    *,
    stream_url: str = "",
    probe_raw: Any = None,
) -> YouTubePoCapture | None:
    """Merge newly captured PO token signals into the session state."""
    base = current or YouTubePoCapture()
    gvs_token = base.gvs_token
    player_token = base.player_token
    video_id = base.video_id

    if stream_url:
        captured_gvs = extract_gvs_token_from_url(stream_url)
        if captured_gvs:
            gvs_token = captured_gvs
            log_platform_browser("YouTube GVS PO token captured from stream URL")

    if probe_raw is not None:
        probe = parse_youtube_po_probe(probe_raw)
        if probe is not None:
            if probe.player_token:
                player_token = probe.player_token
                log_platform_browser("YouTube player PO token captured from page hook")
            if probe.gvs_token:
                gvs_token = probe.gvs_token
            if probe.video_id:
                video_id = probe.video_id

    merged = YouTubePoCapture(
        gvs_token=gvs_token,
        player_token=player_token,
        video_id=video_id,
    )
    if merged == base and current is not None:
        return current
    if not merged.usable_for_ytdlp() and not merged.video_id:
        return current
    return merged


def build_youtube_extractor_args(capture: YouTubePoCapture | None) -> dict[str, list[str]]:
    """Build yt-dlp YouTube extractor_args for PO tokens or cookie fallbacks."""
    if capture is not None and capture.usable_for_ytdlp():
        po_tokens: list[str] = []
        if capture.gvs_token.strip():
            po_tokens.append(f"mweb.gvs+{capture.gvs_token.strip()}")
        if capture.player_token.strip():
            po_tokens.append(f"mweb.player+{capture.player_token.strip()}")
        return {
            "player_client": ["mweb"],
            "po_token": po_tokens,
        }
    return {
        "player_client": ["tv", "web_safari"],
    }


def is_youtube_po_error(exc: Exception) -> bool:
    """Return True when yt-dlp failed because a PO token was required."""
    text = str(exc).lower()
    return "po token" in text or "potoken" in text or "proof of origin" in text
