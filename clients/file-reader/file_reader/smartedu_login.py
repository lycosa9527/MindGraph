"""WebView2 login helper for SmartEdu (basic.smartedu.cn)."""

from __future__ import annotations

import json
import threading
from typing import Callable, Optional

SMARTEDU_LOGIN_URL = "https://basic.smartedu.cn"
TOKEN_JS = """
(function() {
  var keys = Object.keys(localStorage).filter(function(k) { return k.indexOf('ND_UC_AUTH') === 0; });
  for (var i = 0; i < keys.length; i++) {
    try {
      var raw = localStorage.getItem(keys[i]);
      if (!raw) continue;
      var tokenData = JSON.parse(raw);
      if (!tokenData || !tokenData.value) continue;
      var parsed = JSON.parse(tokenData.value);
      if (parsed && parsed.access_token) return parsed.access_token;
    } catch (e) {}
  }
  return '';
})()
"""

try:
    import webview
except ImportError:
    webview = None


class SmartEduLoginError(RuntimeError):
    """Raised when login window cannot obtain a token."""


def pywebview_available() -> bool:
    """Return True when pywebview can be imported."""
    return webview is not None


def open_smartedu_login_window(*, on_complete: Optional[Callable[[str], None]] = None) -> None:
    """
    Open SmartEdu login in a WebView2 window.

    Calls on_complete(token_or_empty) when the window closes.
    """
    webview_mod = webview
    if webview_mod is None:
        if on_complete is not None:
            on_complete("")
        return

    token_holder: dict[str, str] = {"token": ""}

    def _collect_token() -> None:
        if not webview_mod.windows:
            return
        try:
            result = webview_mod.windows[0].evaluate_js(TOKEN_JS)
        except (RuntimeError, OSError, ValueError, json.JSONDecodeError):
            token_holder["token"] = ""
            return
        if isinstance(result, str):
            token_holder["token"] = result.strip()

    def _on_closed() -> None:
        _collect_token()
        if on_complete is not None:
            on_complete(token_holder["token"])

    window = webview_mod.create_window(
        "SmartEdu Login",
        SMARTEDU_LOGIN_URL,
        width=960,
        height=720,
        confirm_close=True,
    )
    window.events.closed += _on_closed
    webview_mod.start(gui="edgechromium")


def open_smartedu_login_async(on_complete: Callable[[str], None]) -> threading.Thread:
    """Run login window on a background thread."""
    thread = threading.Thread(
        target=lambda: open_smartedu_login_window(on_complete=on_complete),
        daemon=True,
    )
    thread.start()
    return thread
