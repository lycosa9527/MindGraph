"""CSP host-sources for official WeChat / DingTalk QR widgets.

WeChat 网站应用 (WxLogin.js, audited against the live SDK):

* Parent page (our CSP applies):
  * script: ``https://res.wx.qq.com/connect/zh_CN/htmledition/js/wxLogin.js``
  * iframe: ``https://open.weixin.qq.com/connect/qrconnect?...``
  * postMessage origin is exactly ``https://open.weixin.qq.com``
* Inside that iframe (WeChat's document, not our script-src):
  * static CSS/JS/images on ``res.wx.qq.com``
  * QR status poll ``https://long.open.weixin.qq.com/connect/l/qrconnect``
* Server-only (httpx, not browser CSP): ``api.weixin.qq.com``

``long.open.weixin.qq.com`` is listed on parent ``connect-src`` so a future
WxLogin that polls from the top window still works. It is not listed on
``script-src`` (the poll historically returns JSONP for the iframe window).

Excluded on purpose (different products): ``open.work.weixin.qq.com``
(企业微信), ``mp.weixin.qq.com``, ``wx.qq.com`` / ``login.weixin.qq.com``
(网页微信), ``res2.wx.qq.com`` (JSSDK fallback, not used by wxLogin.js).
"""

from __future__ import annotations

# https://developers.weixin.qq.com/doc/oplatform/Website_App/WeChat_Login/Wechat_Login.html
WECHAT_CSP_SCRIPT_SRC = "https://res.wx.qq.com"
WECHAT_CSP_FRAME_SRC = "https://open.weixin.qq.com"
WECHAT_CSP_CONNECT_SRC = "https://open.weixin.qq.com https://long.open.weixin.qq.com"

# https://open.dingtalk.com/document/orgapp/tutorial-obtaining-user-personal-information
DINGTALK_CSP_SCRIPT_SRC = "https://g.alicdn.com"
DINGTALK_CSP_FRAME_SRC = "https://login.dingtalk.com"
DINGTALK_CSP_CONNECT_SRC = "https://login.dingtalk.com"

OAUTH_QR_CSP_SCRIPT_SRC = f"{WECHAT_CSP_SCRIPT_SRC} {DINGTALK_CSP_SCRIPT_SRC}"
OAUTH_QR_CSP_FRAME_SRC = f"{WECHAT_CSP_FRAME_SRC} {DINGTALK_CSP_FRAME_SRC}"
OAUTH_QR_CSP_CONNECT_SRC = f"{WECHAT_CSP_CONNECT_SRC} {DINGTALK_CSP_CONNECT_SRC}"

# Hosts that must never be treated as 网站应用 login CSP (wrong product).
WECHAT_CSP_EXCLUDED_HOSTS = (
    "https://open.work.weixin.qq.com",
    "https://mp.weixin.qq.com",
    "https://wx.qq.com",
    "https://login.weixin.qq.com",
    "https://res2.wx.qq.com",
)


def oauth_qr_csp_extra(hosts: str) -> str:
    """Leading-space host list for appending onto a CSP directive."""
    return f" {hosts}"
