"""WeChat Channels URL parsing and capture helpers."""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from file_reader.wechat_channels.models import CapturedChannelVideo

_CHANNELS_HOSTS = ("channels.weixin.qq.com",)
_STODOWNLOAD_RE = re.compile(
    r"https?://[^\s\"'<>]*(?:finder\.video\.qq\.com|wxapp\.tc\.qq\.com)[^\s\"'<>]*stodownload[^\s\"'<>]*",
    re.IGNORECASE,
)
_VIDEO_ID_RE = re.compile(r"(?:export/|feed/|finder/)?([A-Za-z0-9_-]{8,})")


def is_channels_page(raw_url: str) -> bool:
    """Return True for WeChat Channels web pages."""
    text = (raw_url or "").strip()
    if not text.startswith(("http://", "https://")):
        text = f"https://{text}"
    host = (urlparse(text).hostname or "").lower()
    return any(host == item or host.endswith(f".{item}") for item in _CHANNELS_HOSTS)


def is_channels_media_url(raw_url: str) -> bool:
    """Return True when a network URL looks like a Channels CDN asset."""
    text = (raw_url or "").strip()
    if not text:
        return False
    return bool(_STODOWNLOAD_RE.search(text))


def normalize_channels_media_url(raw_url: str) -> str:
    """Return a cleaned Channels CDN URL."""
    text = (raw_url or "").strip()
    match = _STODOWNLOAD_RE.search(text)
    return match.group(0) if match else text


def _parse_video_object(payload: dict) -> CapturedChannelVideo | None:
    media_list = payload.get("media")
    if not isinstance(media_list, list) or not media_list:
        return None
    media = media_list[0]
    if not isinstance(media, dict):
        return None
    base_url = str(media.get("url") or "").strip()
    token = str(media.get("url_token") or "").strip()
    media_url = f"{base_url}{token}" if base_url else ""
    if not media_url:
        return None
    decode_key = str(media.get("decode_key") or "").strip()
    object_desc = payload.get("object_desc")
    title = ""
    if isinstance(object_desc, dict):
        title = str(object_desc.get("description") or "").strip()
    nickname = str(payload.get("nickname") or payload.get("username") or "").strip()
    video_id = str(payload.get("object_id") or payload.get("id") or "").strip()
    if not video_id:
        match = _VIDEO_ID_RE.search(media_url)
        video_id = match.group(1) if match else ""
    return CapturedChannelVideo(
        video_id=video_id or media_url[-24:],
        title=title or nickname or "channels-video",
        media_url=media_url,
        decode_key=decode_key,
        uploader=nickname,
    )


def _extract_object_from_payload(payload: dict) -> dict | None:
    if isinstance(payload.get("object"), dict):
        return payload["object"]
    data = payload.get("data")
    if isinstance(data, dict):
        if isinstance(data.get("object"), dict):
            return data["object"]
        object_desc = data.get("object_desc")
        if isinstance(object_desc, dict):
            return {"object_desc": object_desc, "nickname": data.get("nickname", "")}
    return None


def parse_channels_capture_entry(raw: object) -> CapturedChannelVideo | None:
    """Parse one hook capture entry or API JSON blob."""
    if isinstance(raw, dict):
        if raw.get("media_url"):
            return CapturedChannelVideo(
                video_id=str(raw.get("video_id") or raw.get("id") or ""),
                title=str(raw.get("title") or raw.get("description") or "channels-video"),
                media_url=str(raw.get("media_url") or ""),
                decode_key=str(raw.get("decode_key") or ""),
                uploader=str(raw.get("uploader") or raw.get("nickname") or ""),
            )
        obj = _extract_object_from_payload(raw)
        if isinstance(obj, dict):
            return _parse_video_object(obj)
        return None
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            return parse_channels_capture_entry(parsed)
    return None


def merge_channels_captures(
    current: tuple[CapturedChannelVideo, ...],
    *,
    hook_raw: object = None,
    network_url: str = "",
) -> tuple[CapturedChannelVideo, ...]:
    """Merge hook/network captures into a de-duplicated tuple."""
    items: list[CapturedChannelVideo] = list(current)
    seen = {item.asset_id() for item in items}

    def append(item: CapturedChannelVideo | None) -> None:
        if item is None or not item.media_url:
            return
        asset_id = item.asset_id()
        if asset_id in seen:
            for index, existing in enumerate(items):
                if existing.asset_id() != asset_id:
                    continue
                if item.decode_key and not existing.decode_key:
                    items[index] = item
                elif item.title and existing.title == "channels-video":
                    items[index] = CapturedChannelVideo(
                        video_id=existing.video_id,
                        title=item.title,
                        media_url=existing.media_url,
                        decode_key=item.decode_key or existing.decode_key,
                        uploader=item.uploader or existing.uploader,
                    )
                return
            return
        seen.add(asset_id)
        items.append(item)

    if hook_raw is not None:
        if isinstance(hook_raw, list):
            for entry in hook_raw:
                append(parse_channels_capture_entry(entry))
        else:
            append(parse_channels_capture_entry(hook_raw))

    if network_url:
        cleaned = normalize_channels_media_url(network_url)
        append(
            CapturedChannelVideo(
                video_id=cleaned[-24:],
                title="channels-video",
                media_url=cleaned,
            ),
        )
    return tuple(items)


CHANNELS_HOOK_JS = """
(function() {
  if (window.__mgChannelsHookInstalled) return 'ok';
  window.__mgChannelsHookInstalled = true;
  window.__mgChannelsVideos = window.__mgChannelsVideos || [];

  function pushVideo(entry) {
    if (!entry || !entry.media_url) return;
    for (var i = 0; i < window.__mgChannelsVideos.length; i++) {
      var cur = window.__mgChannelsVideos[i];
      if (cur.media_url === entry.media_url) {
        if (entry.decode_key && !cur.decode_key) window.__mgChannelsVideos[i] = entry;
        return;
      }
    }
    window.__mgChannelsVideos.push(entry);
  }

  function parseApiText(text) {
    if (!text) return;
    try {
      var payload = JSON.parse(text);
    } catch (e) {
      return;
    }
    var object = payload && payload.object;
    if (!object && payload && payload.data && payload.data.object) {
      object = payload.data.object;
    }
    if (!object || !object.object_desc || !object.object_desc.media) return;
    var media = object.object_desc.media[0] || {};
    var url = (media.url || '') + (media.url_token || '');
    if (!url) return;
    pushVideo({
      video_id: String(object.object_id || object.id || ''),
      title: String(object.object_desc.description || object.nickname || 'channels-video'),
      media_url: url,
      decode_key: String(media.decode_key || ''),
      uploader: String(object.nickname || '')
    });
  }

  var origFetch = window.fetch;
  if (origFetch) {
    window.fetch = function(input, init) {
      var promise = origFetch.apply(this, arguments);
      try {
        var url = (typeof input === 'string') ? input : (input && input.url) || '';
        if (url.indexOf('channels.weixin.qq.com') !== -1) {
          promise.then(function(resp) {
            resp.clone().text().then(parseApiText).catch(function() {});
          }).catch(function() {});
        } else if (init && init.body && typeof init.body === 'string') {
          parseApiText(init.body);
        }
      } catch (e) {}
      return promise;
    };
  }

  var origOpen = XMLHttpRequest.prototype.open;
  var origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url) {
    this.__mgChannelsUrl = url || '';
    return origOpen.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function(body) {
    var self = this;
    this.addEventListener('load', function() {
      try {
        if ((self.__mgChannelsUrl || '').indexOf('channels.weixin.qq.com') !== -1) {
          parseApiText(self.responseText || '');
        } else if (typeof body === 'string') {
          parseApiText(body);
        }
      } catch (e) {}
    });
    return origSend.apply(this, arguments);
  };
  return 'ok';
})()
"""

CHANNELS_READ_JS = """
(function() {
  return JSON.stringify(window.__mgChannelsVideos || []);
})()
"""

CHANNELS_KEYSTREAM_JS = """
(function(decodeKey) {
  var key = String(decodeKey || '').trim();
  if (!key) return '';
  window.__mgChannelsKeystream = window.__mgChannelsKeystream || {};
  if (window.__mgChannelsKeystream[key]) return window.__mgChannelsKeystream[key];
  try {
    if (typeof Module !== 'undefined' && Module._malloc && Module._free) {
      var candidates = [
        '_wasm_isaac_generate',
        '_isaac_generate',
        'wasm_isaac_generate'
      ];
      for (var i = 0; i < candidates.length; i++) {
        var fnName = candidates[i];
        if (typeof Module[fnName] !== 'function') continue;
        var size = 131072;
        var ptr = Module._malloc(size);
        Module[fnName](parseInt(key, 10), ptr, size);
        var arr = new Uint8Array(Module.HEAPU8.buffer, ptr, size);
        var reversed = Array.from(arr).reverse();
        Module._free(ptr);
        var hex = reversed.map(function(b) {
          return ('0' + b.toString(16)).slice(-2);
        }).join('');
        window.__mgChannelsKeystream[key] = hex;
        return hex;
      }
    }
  } catch (e) {}
  return '';
})()
"""

CHANNELS_CLEANUP_JS = """
(function() {
  try {
    delete window.__mgChannelsHookInstalled;
    delete window.__mgChannelsVideos;
  } catch (e) {}
  return 'ok';
})()
"""
