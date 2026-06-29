"""Platform browser helpers — URLs, login probes, storage paths."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from file_reader.settings import SETTINGS_DIR

DEFAULT_HOME_URL = "https://basic.smartedu.cn/"

LOGIN_STATE_JS = """
(function() {
  var host = (location.hostname || '').toLowerCase();
  var cookies = document.cookie || '';
  var result = {
    smartedu_logged_in: false,
    baidu_logged_in: false,
    doc360_logged_in: false,
    bilibili_logged_in: false,
    youtube_logged_in: false,
    douyin_logged_in: false,
    tiktok_logged_in: false,
    wechat_channels_logged_in: false,
    tencent_meeting_logged_in: false,
    access_token: ''
  };
  var keys = Object.keys(localStorage).filter(function(k) {
    return k.indexOf('ND_UC_AUTH') === 0;
  });
  for (var i = 0; i < keys.length; i++) {
    try {
      var raw = localStorage.getItem(keys[i]);
      if (!raw) continue;
      var tokenData = JSON.parse(raw);
      if (!tokenData || !tokenData.value) continue;
      var parsed = JSON.parse(tokenData.value);
      if (parsed && parsed.access_token) {
        result.access_token = parsed.access_token;
        result.smartedu_logged_in = true;
        break;
      }
    } catch (e) {}
  }
  if (cookies.indexOf('BDUSS=') !== -1) {
    result.baidu_logged_in = true;
  }
  if (/360doc/i.test(host)) {
    if (cookies.match(/(?:^|;\\s*)(userid|MyLogin|360doc[^=]*session|loginuserid)/i)) {
      result.doc360_logged_in = true;
    }
  }
  if (/bilibili/i.test(host) && /SESSDATA=/.test(cookies)) {
    result.bilibili_logged_in = true;
  }
  if (/douyin/i.test(host) && (/ttwid=/.test(cookies) || /sessionid=/.test(cookies))) {
    result.douyin_logged_in = true;
  }
  if (/tiktok/i.test(host) && (/tt_chain_token=/.test(cookies) || /sessionid=/.test(cookies))) {
    result.tiktok_logged_in = true;
  }
  if (/channels\\.weixin\\.qq\\.com/i.test(host)) {
    if (/(?:^|;\\s*)(wxuin|sessionid|webwx_data_ticket|pass_ticket)=/i.test(cookies)) {
      result.wechat_channels_logged_in = true;
    }
  }
  if (/youtube/i.test(host) || /youtu\\.be/i.test(host)) {
    if (/LOGIN_INFO=/.test(cookies) || /SID=/.test(cookies) || /__Secure-3PSID=/.test(cookies)) {
      result.youtube_logged_in = true;
    }
  }
  if (/meeting\\.tencent\\.com/i.test(host)) {
    if (/(?:^|;\\s*)(wxuin|nova_openid|app_uid|userid|tk|token)=/i.test(cookies)) {
      result.tencent_meeting_logged_in = true;
    }
  }
  return JSON.stringify(result);
})()
"""


def browser_storage_path() -> Path:
    """Directory for embedded WebView2 cookies, localStorage, and cache."""
    path = SETTINGS_DIR / "platform-browser" / "webview2"
    path.mkdir(parents=True, exist_ok=True)
    return path


def playwright_storage_path() -> Path:
    """Directory for Playwright persistent Chromium profile data."""
    path = SETTINGS_DIR / "platform-browser" / "playwright-edge"
    path.mkdir(parents=True, exist_ok=True)
    return path


def configure_webview_storage(path: Path) -> str:
    """Point WebView2 at a persistent user-data folder before widget creation."""
    resolved = path.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    folder = str(resolved)
    os.environ["WEBVIEW2_USER_DATA_FOLDER"] = folder
    return folder


def normalize_nav_url(raw: str) -> str:
    """Return a navigable http(s) URL from address-bar text."""
    text = (raw or "").strip()
    if not text:
        return DEFAULT_HOME_URL
    if re.match(r"^https?://", text, flags=re.IGNORECASE):
        return text
    if " " in text:
        raise ValueError("Invalid URL")
    if "." in text:
        return f"https://{text}"
    raise ValueError("Invalid URL")


def merge_cookie_login_flags(state: dict[str, Any], cookies: Any) -> dict[str, Any]:
    """Augment JS login state with HttpOnly / cross-site cookies from WebView."""
    merged = dict(state)
    if not cookies:
        return merged
    for cookie in cookies:
        name = str(getattr(cookie, "name", "") or "")
        domain = str(getattr(cookie, "domain", "") or "").lower()
        if name == "BDUSS":
            merged["baidu_logged_in"] = True
        if name == "SESSDATA" and "bilibili" in domain:
            merged["bilibili_logged_in"] = True
        if "douyin" in domain and name in {"ttwid", "sessionid", "sid_guard"}:
            merged["douyin_logged_in"] = True
        if "tiktok" in domain and name in {"sessionid", "tt_chain_token", "sid_tt"}:
            merged["tiktok_logged_in"] = True
        if "channels.weixin.qq.com" in domain and name in {
            "wxuin",
            "sessionid",
            "webwx_data_ticket",
            "pass_ticket",
        }:
            merged["wechat_channels_logged_in"] = True
        if "youtube" in domain and name in {
            "LOGIN_INFO",
            "SID",
            "__Secure-3PSID",
            "__Secure-1PSID",
        }:
            merged["youtube_logged_in"] = True
        if "meeting.tencent.com" in domain and name.lower() in {
            "wxuin",
            "nova_openid",
            "app_uid",
            "userid",
            "tk",
            "token",
        }:
            merged["tencent_meeting_logged_in"] = True
        if "360doc" in domain and name.lower() in {
            "userid",
            "mylogin",
            "loginuserid",
        }:
            merged["doc360_logged_in"] = True
    return merged


def parse_login_state(raw: Any) -> dict[str, Any]:
    """Parse LOGIN_STATE_JS evaluate_js result."""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
